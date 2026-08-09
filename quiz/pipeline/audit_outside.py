#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复查 B2：还有多少町丁的代表点落在所有市町村多边形之外。

裁剪之前是 1,255 个，怀疑主要就是伸进海里的水面調査区。
这里对裁剪后 + 补上米原市的数据重算一遍。
注意：地图上町丁一级的市町村名早就改成读町丁自带的 e-Stat CITY 码了，
所以这个数字只是数据质量指标，不影响显示。
"""
import json, collections
from shapely.geometry import shape
from shapely.strtree import STRtree

KILL = set(json.load(open("/home/user/osm/cho_drop.json")))   # 已删的水面残骸不算
mn = json.load(open("/home/user/-transit/quiz/muni_names.json"))

munis = []
with open("/home/user/osm/jp_muni_final2.geojsonl") as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        g = shape(json.loads(s)["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        munis.append(g)
tree = STRtree(munis)
print("市町村多边形", len(munis), flush=True)

out = collections.Counter()
n = miss = 0
with open("/home/user/osm/ka_clip2.geojsonl") as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        if ft["properties"].get("idx") in KILL:
            continue
        p = shape(ft["geometry"]).representative_point()
        n += 1
        if not any(munis[i].contains(p) for i in tree.query(p)):
            miss += 1
            pr = ft["properties"]["pref"]
            out["%02d%s %s" % (pr, ft["properties"]["city"],
                               mn.get("%02d%s" % (pr, ft["properties"]["city"]), "?"))] += 1
print("町丁 %d，代表点落在所有市町村之外 %d（%.3f%%）" % (n, miss, 100 * miss / n))
for k, v in out.most_common(15):
    print("   %-20s %d" % (k, v))
