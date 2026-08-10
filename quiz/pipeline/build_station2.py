#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""駅第三版：每条线各有自己的站点，但名字只写一次。

用户：「我的藍線難波，被弄到哪裡去了？」

前情：N02 的駅是**按事業者×路線**给的，難波有 4 条记录——
  御堂筋線 135.50016 / 四つ橋線 135.49758 / 千日前線 135.49926 / 南海本線 135.50234
第一版直接画，一个站叠 4 个点，用户报「一个站点却标了两个三个四个点」。
第二版按官方駅グループ + 同名 500m 合成**一个**点，重名是没有了，
但合并点落在御堂筋線（红线）上，四つ橋線（蓝线）那一段就空了——
四つ橋線的なんば比御堂筋線偏西 235 米，是实打实的另一个站厅。

第三版把两个要求拆开满足：
  **点**  按 (駅グループ, 路線) 出，每条线在自己的线上都有一个站点。
          缩小时（z13 以下）只画代表点，免得又变成一堆重叠的点；
          放大到 z13 以上四条线各画各的，蓝线上就有なんば了。
  **名字** 永远只写一次——同名 500m 内聚成一簇，只有代表点带 lab=1。

代表点选谁：簇里线路数最多的那个，并列时取离簇中心最近的。
（難波 簇里御堂筋線/四つ橋線/千日前線 各 1 条、南海本線 1 条，
  最后落到离中心最近的那个，名字不会跑到边上去。）

顺带把「駅の範囲」线段也重出一份，带上路線名——
上一版吸附是按**駅名**找线段的，同名不同线的站（正是難波这种）会互相吸错。
现在每个站点只在**自己那条路線**的线段上找落点，不可能吸到隔壁线上。
"""
import json, math, collections

S = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad"
SRC = S + "/n02/UTF-8/N02-24_Station.geojson"
KX, KY = 91.0, 111.0        # 1° 换算成 km（日本纬度附近）


def pts(g):
    c = g["coordinates"]
    return c if g["type"] == "LineString" else [x for l in c for x in l]


d = json.load(open(SRC, encoding="utf-8"))
recs = []
for f in d["features"]:
    p = f["properties"]
    nm = p.get("N02_005")
    if not nm:
        continue
    g = p.get("N02_005g") or ("c:" + str(p.get("N02_005c")))
    recs.append({"n": nm, "g": g, "ln": p.get("N02_003") or "",
                 "op": p.get("N02_004") or "", "cls": p.get("N02_002"),
                 "pts": pts(f["geometry"]), "geom": f["geometry"]})
print("N02 駅记录 %d 条" % len(recs))

# ── 站台节点：同一个駅グループ里，一条路線算一个 ──
byp = collections.defaultdict(list)
for r in recs:
    byp[(r["g"], r["op"], r["ln"])].append(r)
plats = []
for (g, op, ln), rs in byp.items():
    ps = [q for r in rs for q in r["pts"]]
    xs = [q[0] for q in ps]
    ys = [q[1] for q in ps]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    # 落到自己这条线的线段上（駅线段本来就画在自己的轨道上）
    best, bd = None, 1e18
    for r in rs:
        for c in ([r["geom"]["coordinates"]] if r["geom"]["type"] == "LineString"
                  else r["geom"]["coordinates"]):
            for i in range(len(c) - 1):
                x1, y1 = c[i]
                x2, y2 = c[i + 1]
                dx, dy = (x2 - x1) * KX, (y2 - y1) * KY
                d2 = dx * dx + dy * dy
                t = 0.0 if d2 == 0 else max(0.0, min(1.0,
                    (((cx - x1) * KX) * dx + ((cy - y1) * KY) * dy) / d2))
                px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                dd = ((px - cx) * KX) ** 2 + ((py - cy) * KY) ** 2
                if dd < bd:
                    bd, best = dd, (px, py)
    x, y = best if best else (cx, cy)
    plats.append({"n": rs[0]["n"], "g": g, "op": op, "ln": ln,
                  "cls": rs[0]["cls"], "x": x, "y": y, "nrec": len(rs)})
print("站台节点 %d 个（原来合并成 %d 个駅点）" % (len(plats), len(byp)))

# ── 聚簇：同名 + 500m 以内算同一个駅（只影响「名字写在哪」）──
R = 0.0055
grid = collections.defaultdict(list)
for i, q in enumerate(plats):
    grid[(int(q["x"] / R), int(q["y"] / R))].append(i)
par = list(range(len(plats)))


def find(a):
    while par[a] != a:
        par[a] = par[par[a]]
        a = par[a]
    return a


def uni(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        par[rb] = ra


for i, q in enumerate(plats):
    gx, gy = int(q["x"] / R), int(q["y"] / R)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in grid.get((gx + dx, gy + dy), ()):
                if j <= i or plats[j]["n"] != q["n"]:
                    continue
                if math.hypot((plats[j]["x"] - q["x"]) * KX,
                              (plats[j]["y"] - q["y"]) * KY) > 0.5:
                    continue
                uni(i, j)

clus = collections.defaultdict(list)
for i in range(len(plats)):
    clus[find(i)].append(i)
print("聚成 %d 个駅（名字按这个数写）" % len(clus))

# ── 客流：S12 按「駅名 + 事業者」配到各自的站台上 ──
try:
    s12 = json.load(open(S + "/s12/UTF-8/S12-23_NumberOfPassengers.geojson",
                         encoding="utf-8"))
except Exception:
    s12 = {"features": []}
prec = []
for f in s12["features"]:
    p = f["properties"]
    v = p.get("S12_053")
    if not isinstance(v, (int, float)) or v <= 0:
        continue
    ps = pts(f["geometry"]) if f["geometry"]["type"] != "Point" else [f["geometry"]["coordinates"]]
    prec.append((p.get("S12_001") or "", p.get("S12_002") or "",
                 sum(q[0] for q in ps) / len(ps), sum(q[1] for q in ps) / len(ps), int(v)))
pgrid = collections.defaultdict(list)
for i, (nm, op, x, y, v) in enumerate(prec):
    pgrid[(int(x * 100), int(y * 100))].append(i)
print("S12 有客流的记录 %d 条" % len(prec))

used = set()
for i, q in enumerate(plats):
    s = 0
    gx, gy = int(q["x"] * 100), int(q["y"] * 100)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in pgrid.get((gx + dx, gy + dy), ()):
                if j in used:
                    continue
                nm, op, x, y, v = prec[j]
                if nm != q["n"]:
                    continue
                # 事業者对得上优先；S12 和 N02 的事業者名偶有出入，
                # 对不上就退回「同名 + 1.5km 内」，宁可算上也不要漏
                if op and q["op"] and op != q["op"]:
                    continue
                if math.hypot((x - q["x"]) * KX, (y - q["y"]) * KY) > 1.5:
                    continue
                used.add(j)
                s += v
    q["pax"] = s
# 第二轮：事業者名对不上而没配到的，按同名近邻兜底
for i, q in enumerate(plats):
    if q["pax"]:
        continue
    gx, gy = int(q["x"] * 100), int(q["y"] * 100)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in pgrid.get((gx + dx, gy + dy), ()):
                if j in used:
                    continue
                nm, op, x, y, v = prec[j]
                if nm != q["n"]:
                    continue
                if math.hypot((x - q["x"]) * KX, (y - q["y"]) * KY) > 1.5:
                    continue
                used.add(j)
                q["pax"] += v

# ── 定簇的 rank / 代表点 / 簇客流 ──
out = open(S + "/tr_station_p.geojsonl", "w")
nlab = 0
for root, idx in clus.items():
    rank = len({(plats[i]["op"], plats[i]["ln"]) for i in idx})
    tot = sum(plats[i]["pax"] for i in idx)
    cx = sum(plats[i]["x"] for i in idx) / len(idx)
    cy = sum(plats[i]["y"] for i in idx) / len(idx)
    # 代表点＝记录最多的；并列取离簇中心最近的，免得名字跑到最边上那个站台去
    rep = max(idx, key=lambda i: (plats[i]["nrec"],
              -math.hypot((plats[i]["x"] - cx) * KX, (plats[i]["y"] - cy) * KY)))
    ops = "、".join(sorted({plats[i]["op"] for i in idx}))[:60]
    lns = "、".join(sorted({plats[i]["ln"] for i in idx}))[:80]
    for i in idx:
        p = {"n": plats[i]["n"], "rank": rank,
             "lab": 1 if i == rep else 0,
             "ln": lns if i == rep else plats[i]["ln"],
             "op": ops if i == rep else plats[i]["op"]}
        if i == rep:
            p["pax"] = tot
            nlab += 1
        elif plats[i]["pax"]:
            p["pax"] = plats[i]["pax"]
        out.write(json.dumps({"type": "Feature", "properties": p,
                              "geometry": {"type": "Point",
                                           "coordinates": [round(plats[i]["x"], 6),
                                                           round(plats[i]["y"], 6)]}},
                             ensure_ascii=False) + "\n")
out.close()

# ── 駅の範囲：原样出，带上 rank 供分级 ──
rank_of = {}
for root, idx in clus.items():
    r = len({(plats[i]["op"], plats[i]["ln"]) for i in idx})
    for i in idx:
        rank_of[(plats[i]["g"], plats[i]["op"], plats[i]["ln"])] = r
seg = open(S + "/tr_stationseg2.geojsonl", "w")
ns = 0
for r in recs:
    seg.write(json.dumps({"type": "Feature",
                          "properties": {"n": r["n"],
                                         "rank": rank_of.get((r["g"], r["op"], r["ln"]), 1)},
                          "geometry": r["geom"]}, ensure_ascii=False) + "\n")
    ns += 1
seg.close()
print("写出：站台点 %d（其中带名字的 %d）、駅範囲线段 %d" % (len(plats), nlab, ns))

tot = sum(q["pax"] for q in plats)
hit = sum(1 for q in plats if q["pax"])
print("配上客流的站台 %d / %d，合计 %.2f 亿人次/日" % (hit, len(plats), tot / 1e8))
print("難波一带：")
for q in sorted(plats, key=lambda q: -q["pax"]):
    if q["n"] in ("難波", "大阪難波", "JR難波") :
        print("   %-6s %-12s %-16s %.5f,%.5f pax=%d"
              % (q["n"], q["ln"], q["op"], q["x"], q["y"], q["pax"]))
