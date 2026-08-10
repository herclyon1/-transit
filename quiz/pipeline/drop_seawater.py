#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「其实是海」的水体面丢掉，只留真正在陆地里的湖沼。

用户报的：「川崎这块因为人工土地的原因，你有的涂成蓝色了，别涂色，
只要是在海里的都不涂，入海口那边不用管。这是设计美术问题。」

港内的运河和港池在 OSM 里也是 natural=water，被我们当湖沼填了浅蓝，
跟海的底色又不完全一样，于是埋立地之间出现一格一格的蓝块，很难看。

规则：**水体面必须落在陆地里才画。**
OSM 的陆地多边形是按海岸线生成的，内陆湖不挖洞——所以湖在陆地内部，
而运河/港池在陆地外部（它们本来就是海的一部分）。
按「落在陆地内的面积比」判，<50% 的丢掉。河口那种一半一半的照旧留着。
"""
import json, sys
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.ops import unary_union

LAND = "/home/user/osm/jland.geojsonl"
SRC = "/home/user/osm/water_all3.geojsonl"
DST = "/home/user/osm/water_all4.geojsonl"

land = []
for l in open(LAND):
    s = l.replace("\x1e", "").strip()
    if not s:
        continue
    g = shape(json.loads(s)["geometry"])
    if not g.is_valid:
        g = g.buffer(0)
    land.append(g)
tree = STRtree(land)
print("陆地块", len(land), flush=True)

o = open(DST, "w")
n = keep = drop = 0
for l in open(SRC):
    s = l.replace("\x1e", "").strip()
    if not s:
        continue
    f = json.loads(s)
    n += 1
    # 只判日本范围内的（jp=1）；東亜那批陆地多边形不在手边，原样留着
    if f["properties"].get("jp") != 1:
        o.write(json.dumps(f, ensure_ascii=False) + "\n")
        keep += 1
        continue
    try:
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        a = g.area
        if a <= 0:
            raise ValueError
        hit = tree.query(g)
        inside = unary_union([land[i] for i in hit]).intersection(g).area if len(hit) else 0.0
        frac = inside / a
    except Exception:
        frac = 1.0                      # 判不了就留着，宁可多画不要少画
    if frac >= 0.5:
        o.write(json.dumps(f, ensure_ascii=False) + "\n")
        keep += 1
    else:
        drop += 1
    if n % 10000 == 0:
        print("  %d…" % n, flush=True)
o.close()
print("水体 %d → 留 %d，丢掉在海里的 %d" % (n, keep, drop))
