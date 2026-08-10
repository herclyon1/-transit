#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""駅の範囲：直接用 N02 的駅线段画，不再只画一个点。

用户报的：「你这些车站点，出发站不在线的端头，交叉的车站不在线上，强迫症有点难受。
能以实际车站面积显示吗？」

N02 的「鉄道駅」本来就是**沿轨道的一小段线**（这才是官方给的「駅の範囲」），
之前为了合并同名同駅的多条记录把它压成了点。现在两样都出：
  station    合并后的点，负责标注和点击（已吸附到轨道线上，见 snap_station.py）
  stationseg 原始线段，放大之后画成加粗短横杠，永远压在轨道上，不会歪

至于「实际车站面积」——N02 里没有面。真正的站舍/月台面在 OSM，
但日本大站有、小站多半只有一个点，覆盖不齐；一半的站有漂亮的轮廓、
另一半只有一根杠，比现在这样统一还难看。所以不采用。
"""
import json, collections

SRC = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad/n02/UTF-8/N02-24_Station.geojson"
OUT = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad/tr_stationseg.geojsonl"

# 跟 build_transit.py 同一套分类口径
data = json.load(open(SRC, encoding="utf-8"))
feats = data["features"] if isinstance(data, dict) else data
rank = collections.Counter()
for f in feats:
    p = f["properties"]
    rank[p.get("N02_005")] += 1

o = open(OUT, "w")
n = 0
for f in feats:
    p = f["properties"]
    nm = p.get("N02_005") or ""
    g = f["geometry"]
    if not g or g["type"] not in ("LineString", "MultiLineString"):
        continue
    o.write(json.dumps({"type": "Feature",
                        "properties": {"n": nm, "rank": rank[nm]},
                        "geometry": g}, ensure_ascii=False) + "\n")
    n += 1
o.close()
print("駅の範囲（线段）%d 条，涉及駅名 %d 个" % (n, len(rank)))
