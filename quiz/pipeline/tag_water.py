#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给水体/河川打上「属于哪块地」的标记，并丢掉不落在任何已绘制陆地上的。

修两个 bug：
  1.「桦太岛有bug。水系显示问题」——樺太西边的海面上飘着一片河网。
     那是俄方提取时按 140.5–157.5E 的方框抽的，把阿穆尔河口（ハバロフスク地方）
     也带进来了，而大陆本身我们不画，于是河网悬在海上。
  2.「现代日本地图怎么还有桦太岛和千岛群岛的水系显示？」——水体层现在两个视图共用，
     但樺太/千島只在東亜视图里画陆地，現代日本视图里它们不该出现。

做法：逐个要素判它落在哪一类已绘制陆地上
     jp=1 日本（含北方領土——那块两个视图都画）
     jp=0 其他已绘制陆地（東亜各国 + 樺太 + 千島）
     都不沾 → 直接丢掉（就是上面第 1 条那批悬空的）
現代日本视图按 jp=1 过滤，東亜视图不过滤。
"""
import json, sys
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.ops import unary_union


def load(path, key=None):
    gs = []
    for l in open(path):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        f = json.loads(s)
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        gs.append(g)
    return gs


print("载入陆地…", flush=True)
JP = load("/home/user/osm/jp_pref_cut.geojsonl") + load("/home/user/osm/jp_disp_fixed.geojsonl")
OT = load("/home/user/osm/units_osm2.geojsonl") + load("/home/user/osm/ru_units.geojsonl")
print("日本(含北方領土) %d 块，其他已绘制陆地 %d 块" % (len(JP), len(OT)), flush=True)
tj, to = STRtree(JP), STRtree(OT)


def flag(g):
    for i in tj.query(g):
        if JP[i].intersects(g):
            return 1
    for i in to.query(g):
        if OT[i].intersects(g):
            return 0
    return None


for src, dst in [("/home/user/osm/water_all2.geojsonl", "/home/user/osm/water_all3.geojsonl"),
                 ("/home/user/osm/rivers_all2.geojsonl", "/home/user/osm/rivers_all3.geojsonl")]:
    o = open(dst, "w")
    n = kept = drop = jp = 0
    for l in open(src):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        f = json.loads(s)
        n += 1
        try:
            g = shape(f["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            fl = flag(g)
        except Exception:
            fl = 0                       # 判不了就当「其他陆地」，宁可留着
        if fl is None:
            drop += 1
            continue
        f["properties"]["jp"] = fl
        jp += fl
        o.write(json.dumps(f, ensure_ascii=False) + "\n")
        kept += 1
        if n % 20000 == 0:
            print("  %s %d…" % (dst.split("/")[-1], n), flush=True)
    o.close()
    print("%s: %d → 留 %d（日本 %d），丢掉悬空的 %d" %
          (dst.split("/")[-1], n, kept, jp, drop))
