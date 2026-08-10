#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交通图层第二版：航路改用真实航迹、空港按名字合并、补上俄方的航路与机场。

用户报的三件事：
  「为啥那霸空港有三个标签」
      C28 里一个空港常常是好几块面（跑道 / ターミナル / エプロン 各一块），
      111 个面只对应 100 个空港，那覇 3 块、熊本/福岡/稚内 各 4 块，
      每块都出一个标注。按名字合并成一个面就只剩一个标注。
  「轮渡航线不应该是直线，又不是飞机。你看看有没有真实轮渡线能用的。其他地图是怎么解决的。」
      国土数値情報 N09「定期旅客航路」是**示意线**：856 条全部只有 2 个顶点，
      就是两个港之间连一根直线，没有航迹。
      其他地图（几乎所有 OSM 系的）用的是 **OSM 的 route=ferry**——那是人工按实际
      航路画的折线，出港绕防波堤、走水道都画出来了。日本境内 762 条，
      顶点数 10~50 的占大多数。改用这一份。
  「北方领土那边不是有定期航路吗？不在国土数值里那应该在俄罗斯那边数据里」
      对。俄方 OSM 里有 3 条：コルサコフ〜南クリル(国後)〜マロクリリスコエ(色丹)
      〜クリルスク(択捉)，以及 南クリル〜マロクリリスコエ。顶点 78/85/27，都是真航迹。

铁路：日本境内仍用 N02（官方、带事業者与鉄道区分，分类比 OSM 稳）；
      樺太的铁道取自俄方 OSM（サハリン鉄道）。
"""
import json, re, math, collections

S = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad"


def tags(s):
    d = {}
    if not s:
        return d
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"', s):
        d[m.group(1)] = m.group(2)
    return d


def rd(p):
    for l in open(p):
        s = l.replace("\x1e", "").strip()
        if s:
            yield json.loads(s)


# ── 空港：按名字合并 ──
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

grp = collections.OrderedDict()
for f in rd(S + "/tr_air.geojsonl"):
    p = f["properties"]
    grp.setdefault(p["n"], []).append(f)
out = open(S + "/tr_air3.geojsonl", "w")
merged = 0
for n, fs in grp.items():
    p = dict(fs[0]["properties"])
    if len(fs) > 1:
        gs = []
        for x in fs:
            g = shape(x["geometry"])
            gs.append(g if g.is_valid else g.buffer(0))
        g = mapping(unary_union(gs))
        merged += 1
    else:
        g = fs[0]["geometry"]
    out.write(json.dumps({"type": "Feature", "properties": p, "geometry": g},
                         ensure_ascii=False) + "\n")
# 俄方（北方領土 + 樺太）的机场
ru = 0
for f in rd("/home/user/osm/ru_air_raw.geojsonl"):
    t = tags(f["properties"].get("other_tags"))
    nm = t.get("name:ja") or t.get("name:en") or f["properties"].get("name")
    if not nm:
        continue
    out.write(json.dumps({"type": "Feature",
                          "properties": {"n": nm, "kind": "ru", "t": 9},
                          "geometry": f["geometry"]}, ensure_ascii=False) + "\n")
    ru += 1
out.close()
print("空港：%d 个（原 %d 块，合并了 %d 个多块的），另加俄方 %d" %
      (len(grp) + ru, sum(len(v) for v in grp.values()), merged, ru))


# ── 航路：换成 OSM 的真实航迹 ──
def ferries(path, only_ferry=True):
    for f in rd(path):
        p = f["properties"]
        t = tags(p.get("other_tags"))
        if only_ferry and t.get("route") != "ferry" and p.get("route") != "ferry":
            continue
        nm = t.get("name:ja") or p.get("name") or t.get("name:en") or ""
        op = t.get("operator:ja") or t.get("operator") or ""
        g = f["geometry"]
        if g["type"] != "LineString" or len(g["coordinates"]) < 2:
            continue
        yield nm, op, g


rows = []
for nm, op, g in ferries("/home/user/osm/jp_ferry_raw.geojsonl"):
    rows.append({"type": "Feature", "properties": {"n": nm, "op": op, "src": "osm"},
                 "geometry": g})
njp = len(rows)
for nm, op, g in ferries("/tmp/ruferry.geojsonl"):
    rows.append({"type": "Feature", "properties": {"n": nm, "op": op, "src": "osm-ru"},
                 "geometry": g})
print("航路：日本 %d 条 + 俄方 %d 条（全部是真实航迹，不是直线）" % (njp, len(rows) - njp))

# N09 有而 OSM 没有的：两端各 3km 内没有任何 OSM 航路顶点，就算漏了，补一条直线
def pts(g):
    return g["coordinates"] if g["type"] == "LineString" else [c for x in g["coordinates"] for c in x]


cells = collections.defaultdict(list)
for r in rows:
    for x, y in r["geometry"]["coordinates"]:
        cells[(int(x * 20), int(y * 20))].append((x, y))


def near(x, y, km=3.0):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for px, py in cells.get((int(x * 20) + dx, int(y * 20) + dy), ()):
                if math.hypot((px - x) * 91, (py - y) * 111) < km:
                    return True
    return False


add = 0
for f in rd(S + "/tr_ferry.geojsonl"):
    c = pts(f["geometry"])
    a, b = c[0], c[-1]
    if near(a[0], a[1]) and near(b[0], b[1]):
        continue
    f["properties"]["src"] = "n09"
    rows.append(f)
    add += 1
print("       N09 里 OSM 没覆盖到的再补 %d 条（仍是直线，标注 src=n09）" % add)

with open(S + "/tr_ferry3.geojsonl", "w") as o:
    for r in rows:
        o.write(json.dumps(r, ensure_ascii=False) + "\n")
print("       合计 %d 条" % len(rows))
