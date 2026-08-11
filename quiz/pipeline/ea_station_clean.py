#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""车站必须落在画出来的轨道旁边，否则不画。

乌鲁木齐实测：碾子沟、邮政局、哈密路、中桥 四个点在图上孤零零地悬着，
底下一条线都没有。查 OSM：它们是 `railway=station`，是真的站，
但它们所在的那条线在 OSM 里还是 `railway=construction`（在建），
我们的铁路层按规矩不画在建线路——于是站在、线不在。

站点浮在空地上，用户第一反应是「这是什么，什么都不显示」。
规则：**车站 500m 内必须有一条我们画出来的轨道**，否则丢掉。
这条同时兜住了其它国家同类情况（线没测绘、线被当成工业专用线剔除等等）。

500m 这个半径：地铁站厅和轨道中心线一般在 200m 以内，大型编组站的站房
离最近的股道也就三四百米；再大就不是「这个站在这条线上」了。
"""
import json, math, collections

D = "/home/user/osm"
KX, KY = 85.0, 111.0
R_KM = 0.5
CELL = 0.01                    # 约 1km 的网格


def rd(p):
    for l in open(p):
        s = l.replace("\x1e", "").strip()
        if s:
            yield json.loads(s)


# 轨道顶点入网格。只用顶点不用线段：OSM 的轨道顶点很密（几十米一个），
# 用顶点近似足够，省掉逐段求距离。
grid = collections.defaultdict(list)
nv = 0
for f in rd(D + "/ea_rail.geojsonl"):
    g = f["geometry"]
    lines = ([g["coordinates"]] if g["type"] == "LineString"
             else g["coordinates"] if g["type"] == "MultiLineString" else [])
    for c in lines:
        for x, y in c:
            grid[(int(x / CELL), int(y / CELL))].append((x, y))
            nv += 1
print("轨道顶点 %d 个，网格 %d 格" % (nv, len(grid)), flush=True)

keep = []
drop = 0
ex = []
for f in rd(D + "/ea_station.geojsonl"):
    x, y = f["geometry"]["coordinates"]
    gx, gy = int(x / CELL), int(y / CELL)
    ok = False
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for vx, vy in grid.get((gx + dx, gy + dy), ()):
                if math.hypot((vx - x) * KX, (vy - y) * KY) <= R_KM:
                    ok = True
                    break
            if ok:
                break
        if ok:
            break
    if ok:
        keep.append(f)
    else:
        drop += 1
        if len(ex) < 8:
            ex.append(f["properties"].get("n") or "(无名)")

with open(D + "/ea_station.geojsonl", "w") as o:
    for f in keep:
        o.write(json.dumps(f, ensure_ascii=False) + "\n")
print("车站 %d → %d（丢掉 500m 内没有轨道的 %d 个）" % (len(keep) + drop, len(keep), drop))
print("被丢掉的例子：", ex)
named = sum(1 for f in keep if f["properties"].get("n"))
print("剩下的里有名字的 %d（%.1f%%）" % (named, 100 * named / max(len(keep), 1)))
