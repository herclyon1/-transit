#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量出每个候选町丁到底有多少比例压在陆地上。

上一轮几何裁剪翻车（町田市 -19.3%、相原町整个消失）是因为拿 23.2 万个町丁
去跑 GEOS 布尔运算，静默失败根本查不过来。这次只算 635 个候选 + 300 个对照，
对照组是人口>500 的实心陆地块——它们的陆地占比必须接近 1，
跑出来不接近就说明这轮几何运算本身不可信，直接放弃这条路。
"""
import json, sys
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.ops import unary_union

print("载入陆地多边形…", flush=True)
land = []
with open("/home/user/osm/jland.geojsonl") as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        g = shape(json.loads(s)["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        land.append(g)
print("陆地块", len(land), flush=True)
tree = STRtree(land)

out = {}
fail = []
n = 0
with open("/home/user/osm/probe.geojsonl") as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        idx = ft["properties"]["idx"]
        g = shape(ft["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        a = g.area
        if a <= 0:
            fail.append((idx, "零面积"))
            continue
        hit = tree.query(g)
        ia = 0.0
        try:
            if len(hit):
                ia = unary_union([land[i] for i in hit]).intersection(g).area
        except Exception as e:
            fail.append((idx, str(e)[:60]))
            continue
        out[idx] = ia / a
        n += 1
        if n % 100 == 0:
            print("  %d…" % n, flush=True)

json.dump(out, open("/home/user/osm/landfrac.json", "w"))
print("算出 %d，失败 %d" % (len(out), len(fail)))
for x in fail[:20]:
    print("  失败", x)
