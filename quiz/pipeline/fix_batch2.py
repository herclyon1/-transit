#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""这一轮真机反馈的三处数据修正。

1)「蓝线的难波跑到红色上面了」
   上一版把駅点吸附到**整个铁路网**里最近的一条线上。换乘站附近几条线交叉，
   最近的那条经常不是这个駅自己的线，于是近鉄的駅被吸到御堂筋線（红线）上去了。
   改成只在**这个駅自己的那些 N02 駅线段**上找落点——駅线段本来就画在自己的线上，
   落点必然在正确的线上。

2)「川崎这块因为人工土地的原因，你有的涂成蓝色了，别涂色，只要是在海里的都不涂」
   港内的运河、港池在 OSM 里也是 natural=water，被我们当湖沼填了浅蓝，
   跟海的底色又不完全一样，埋立地之间就出现一格一格的蓝块。
   规则：**水体必须落在陆地里才画**。湖在陆地多边形内部（陆地多边形不挖湖），
   运河/港池在陆地之外（它们本来就是海）。按落在陆地内的面积比 <50% 就丢掉。

3)「这个缩放下依旧啥也不显示」
   z8 之后県名收掉，市名由 munilab 层画，而那一层的点是**市域代表点**；
   首府圆点用的却是**城市中心点**（OSM 的 place 节点）。京都市两者差了十几公里，
   屏幕上就是一个孤零零的黑点，名字在很远的地方。
   把 47 个県庁所在地的市名点搬到首府圆点上，点和名字就贴在一起了。
"""
import json, math, collections, re

S = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad"
KX, KY = 91.0, 111.0


def rd(p):
    for l in open(p):
        s = l.replace("\x1e", "").strip()
        if s:
            yield json.loads(s)


# ── 1) 駅点落到自己的线上 ──
segs = collections.defaultdict(list)      # 駅名 -> [(x1,y1,x2,y2), ...]
for f in rd(S + "/tr_stationseg.geojsonl"):
    nm = f["properties"]["n"]
    g = f["geometry"]
    lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
    for co in lines:
        for i in range(len(co) - 1):
            a, b = co[i], co[i + 1]
            segs[nm].append((a[0], a[1], b[0], b[1]))


def proj(px, py, x1, y1, x2, y2):
    dx, dy = (x2 - x1) * KX, (y2 - y1) * KY
    d2 = dx * dx + dy * dy
    if d2 == 0:
        return x1, y1, math.hypot((px - x1) * KX, (py - y1) * KY)
    t = max(0.0, min(1.0, ((px - x1) * KX * dx + (py - y1) * KY * dy) / d2))
    qx, qy = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
    return qx, qy, math.hypot((px - qx) * KX, (py - qy) * KY)


out = open(S + "/tr_station4.geojsonl", "w")
n = moved = miss = 0
d = []
for f in rd(S + "/tr_station.geojsonl"):        # 用**未吸附**的原始合并点当起点
    x, y = f["geometry"]["coordinates"]
    nm = f["properties"]["n"]
    n += 1
    best = None
    for s in segs.get(nm, ()):
        q = proj(x, y, *s)
        if best is None or q[2] < best[2]:
            best = q
    if best:
        if best[2] > 0.005:
            moved += 1
            d.append(best[2] * 1000)
        f["geometry"]["coordinates"] = [round(best[0], 7), round(best[1], 7)]
    else:
        miss += 1
    out.write(json.dumps(f, ensure_ascii=False) + "\n")
out.close()
d.sort()
print("駅 %d：落到自己线段上 %d，平移中位 %.0fm / p90 %.0fm / 最大 %.0fm；找不到同名线段 %d"
      % (n, moved, d[len(d) // 2] if d else 0, d[int(len(d) * .9)] if d else 0,
         d[-1] if d else 0, miss))


# ── 3) 県庁所在地的市名点搬到首府点上 ──
cap = {}
for f in rd("/home/user/osm/jp_pref_pt2.geojsonl"):
    p = f["properties"]
    nm = re.sub(r"[（(].*", "", p.get("cap") or "").strip()
    if nm:
        cap[(p["code"], nm)] = f["geometry"]["coordinates"]
o = open("/home/user/osm/jp_muni_pt4.geojsonl", "w")
m = c = 0
for f in rd("/home/user/osm/jp_muni_pt3.geojsonl"):
    p = f["properties"]
    m += 1
    k = (p.get("pref"), p.get("n"))
    if k in cap:
        f["geometry"]["coordinates"] = cap[k]
        p["cap"] = 1
        c += 1
    else:
        p["cap"] = 0
    o.write(json.dumps(f, ensure_ascii=False) + "\n")
o.close()
print("市町村标注点 %d，其中 %d 个県庁所在地已搬到首府圆点上" % (m, c))
