#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把駅点吸附到轨道线上，并另出一份「駅の範囲」线段。

用户报的：「你这些车站点，出发站不在线的端头，交叉的车站不在线上，强迫症有点难受」。

原因：N02 的「鉄道駅」本身是**线**（沿轨道的一小段），不是点。
建数据时为了合并同一个駅的多条记录（難波有 4 条），取了各段代表点的平均，
平均点自然会掉到线外——尤其是换乘站（几条不同走向的线交叉）和终点站
（线的端头，平均往回缩）。

修法两条，都用现成数据，不需要新数据源：
  1. 每个駅点**吸附到最近的轨道线上**（限 300m 内，超了就说明本来就该在那儿，不动）。
     终点站会落在线的端头，换乘站会落在交叉点附近的线上。
  2. 另出一层 `stationseg`：N02 駅记录自己的那段线，按 rank 分级显示。
     放大之后画成加粗的短线段，那才是「駅の範囲」在官方数据里真正的样子。

「能不能按实际车站面积显示」——N02 里没有站的面。真正的站舍/月台面在 OSM 里
（railway=station 的面、platform 面），日本的大站有、小站多半只是个点，覆盖不全，
而且要重新下 2.4GB 的日本提取包。先做上面两条，效果就已经对齐了。
"""
import json, math, collections

S = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad"


def rd(p):
    for l in open(p):
        s = l.replace("\x1e", "").strip()
        if s:
            yield json.loads(s)


# 轨道线的所有线段，按 0.01° 网格索引
segs = collections.defaultdict(list)
nseg = 0
for f in rd(S + "/tr_rail.geojsonl"):
    g = f["geometry"]
    lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
    for co in lines:
        for i in range(len(co) - 1):
            a, b = co[i], co[i + 1]
            nseg += 1
            for k in {(int(a[0] * 100), int(a[1] * 100)), (int(b[0] * 100), int(b[1] * 100))}:
                segs[k].append((a[0], a[1], b[0], b[1]))
print("轨道线段 %d，网格 %d" % (nseg, len(segs)))

KX = 91.0   # 1° 经度 ≈ 91km @ 北纬 35
KY = 111.0


def proj(px, py, x1, y1, x2, y2):
    dx, dy = (x2 - x1) * KX, (y2 - y1) * KY
    d2 = dx * dx + dy * dy
    if d2 == 0:
        return x1, y1, math.hypot((px - x1) * KX, (py - y1) * KY)
    t = ((px - x1) * KX * dx + (py - y1) * KY * dy) / d2
    t = max(0.0, min(1.0, t))
    qx, qy = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
    return qx, qy, math.hypot((px - qx) * KX, (py - qy) * KY)


out = open(S + "/tr_station3.geojsonl", "w")
n = moved = far = 0
dists = []
for f in rd(S + "/tr_station.geojsonl"):
    x, y = f["geometry"]["coordinates"]
    n += 1
    best = None
    gx, gy = int(x * 100), int(y * 100)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for s in segs.get((gx + dx, gy + dy), ()):
                q = proj(x, y, *s)
                if best is None or q[2] < best[2]:
                    best = q
    if best and best[2] < 0.3:            # 300m 以内才吸
        if best[2] > 0.005:               # 超过 5m 才算真的动了
            moved += 1
            dists.append(best[2] * 1000)
        f["geometry"]["coordinates"] = [round(best[0], 7), round(best[1], 7)]
    else:
        far += 1
    out.write(json.dumps(f, ensure_ascii=False) + "\n")
out.close()
dists.sort()
print("駅 %d：吸附 %d 个，平移中位 %.0fm / p90 %.0fm / 最大 %.0fm；300m 内找不到轨道的 %d 个"
      % (n, moved, dists[len(dists) // 2] if dists else 0,
         dists[int(len(dists) * .9)] if dists else 0, dists[-1] if dists else 0, far))
