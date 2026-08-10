#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把港内水面从 都道府県 / 市町村 / 政令市の区 三层的多边形里挖掉。

用户报的：「这个川崎依旧有问题。」
量出来：川崎区的**町丁合起来 39.44 km²（官方 39.49，对）**，
而 OSM 的区界多边形是 **46.13 km²**——多出的 6.69 km² 是川崎港的港池。
于是屏幕上区界那条线跑到海面上去了，而町丁在岸边就停住，两条线对不上。

根因：OSM 的行政界走的是**港湾区域**，把防波堤围起来的水面也圈了进去；
OSM 的陆地多边形同样把这块封闭水域算作陆地（所以之前拿它裁剪毫无作用，
实测裁完还是 46.13）。町丁那边则是靠 water_rule.py 按属性把「水面」調査区删掉的。

修法：**把 water_rule.py 删掉的那 15 块（45.6 km²）从三层行政多边形里减掉**。
它们本来就是 e-Stat 标明的水面調査区，位置和形状都是现成的，不用再猜。
减完 川崎区 46.13 − 6.69 = 39.44，正好等于它自己的町丁合并面积。

守卫：每减一次都必须让该单元的面积**更接近**国土地理院《面積調》；
不满足就整块不减。
"""
import json, math, collections
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

MEN = json.load(open("/home/user/osm/mencho.json"))
KILL = set(json.load(open("/home/user/osm/cho_drop.json")))
MN = json.load(open("/home/user/-transit/quiz/muni_names.json"))


def km2(g, lat=None):
    if lat is None:
        lat = (g.bounds[1] + g.bounds[3]) / 2
    return g.area * (111.32 ** 2) * math.cos(math.radians(lat))


# 收集要挖掉的水面块
holes = []
with open("/home/user/osm/ka_clip2.geojsonl") as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        if ft["properties"].get("idx") in KILL:
            g = shape(ft["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            holes.append(g)
print("要挖掉的水面块 %d，合计 %.1f km²" % (len(holes), sum(km2(g) for g in holes)))
HOLE = unary_union(holes)


def run(src, out, code_of, tag):
    o = open(out, "w")
    n = cut = skip = 0
    for l in open(src):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        n += 1
        g = shape(ft["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        if g.intersects(HOLE):
            code = code_of(ft["properties"])
            t = (MEN.get(code) or {}).get("area")
            try:
                ng = g.difference(HOLE)
            except Exception:
                ng = None
            ok = ng is not None and not ng.is_empty
            if ok and t:                       # 有官方面积就必须变得更准
                ok = abs(km2(ng) - t) < abs(km2(g) - t)
            if ok:
                a0, a1 = km2(g), km2(ng)
                ft["geometry"] = mapping(ng)
                cut += 1
                print("   %s %-12s %8.2f → %8.2f  官方 %s" %
                      (tag, ft["properties"].get("n"), a0, a1, ("%.2f" % t) if t else "-"))
            else:
                skip += 1
        o.write(json.dumps(ft, ensure_ascii=False) + "\n")
    o.close()
    print("[%s] %d 个，挖掉 %d，跳过 %d" % (tag, n, cut, skip))


# 都道府県：官方码 = pref*1000
run("/home/user/osm/jp_pref_final.geojsonl", "/home/user/osm/jp_pref_cut.geojsonl",
    lambda p: "%02d000" % p["code"], "県")
# 市町村：按 muni_names 反查码
REV = collections.defaultdict(list)
for c, nm in MN.items():
    REV[(int(c[:2]), nm)].append(c)
def muni_code(p):
    for c in REV.get((p["pref"], p["n"]), []):
        if c in MEN and not MEN[c]["name"].startswith("("):
            return c
    return None
run("/home/user/osm/jp_muni_final2.geojsonl", "/home/user/osm/jp_muni_cut.geojsonl",
    muni_code, "市町村")
# 区：官方表里名字写成「(母市)区名」
KU = {}
for c, m in MEN.items():
    if m["name"].startswith("("):
        shi, ku = m["name"][1:].split(")")
        KU[(m["pref"], shi, ku)] = c
run("/home/user/osm/jp_ku_clip.geojsonl", "/home/user/osm/jp_ku_cut.geojsonl",
    lambda p: KU.get((None, p.get("shi"), p["n"])) or
              next((c for (pf, shi, ku), c in KU.items()
                    if shi == p.get("shi") and ku == p["n"]), None), "区")
