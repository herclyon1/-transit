#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给每个駅配上乗降客数（一天的上下车人次）。

用户问：「按客流量排序的车站能行吗？梅田难波天王寺鹤桥什么的，
问题就是到第几名的时候截止，不能说鹤桥以下的车站不是市中心吧。」
「每个车站你有客流量当权重吗？」

现在有了。国土数値情報 **S12「駅別乗降客数」**（官方免费，10,500 条记录），
最新一年的字段是 S12_053。

用法不是排序取前 N 名，而是**当权重**：
  某个町丁的通勤便利度 = Σ（各駅的乗降客数 × 到该駅的时间衰减）
梅田权重最大、鶴橋次之、每天几百人的小站权重接近 0，
**不需要在第几名截止**，也就没有「凭什么鶴橋算市中心」这种争论。

S12 是**按事業者×路線**给的（跟 N02 一样），所以先按駅名+位置合到
我们那 9,030 个合并后的駅上，同一个駅的各家事業者相加。
"""
import json, math, collections

S = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad"
SRC = S + "/s12/UTF-8/S12-23_NumberOfPassengers.geojson"
PAX = "S12_053"          # 最新年度の乗降客数
KX, KY = 91.0, 111.0


def mid(g):
    if g["type"] == "LineString":
        c = g["coordinates"]
    elif g["type"] == "MultiLineString":
        c = [x for l in g["coordinates"] for x in l]
    elif g["type"] == "Point":
        return g["coordinates"]
    else:
        c = [x for l in g["coordinates"] for x in l]
    return [sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)]


rec = []
d = json.load(open(SRC, encoding="utf-8"))
for f in d["features"]:
    p = f["properties"]
    v = p.get(PAX)
    if not isinstance(v, (int, float)) or v <= 0:
        continue
    x, y = mid(f["geometry"])
    rec.append((p["S12_001"], x, y, int(v), p.get("S12_002") or ""))
print("S12 有乗降客数的记录 %d 条，合计 %.1f 亿人次/日"
      % (len(rec), sum(r[3] for r in rec) / 1e8))

cells = collections.defaultdict(list)
for i, (nm, x, y, v, op) in enumerate(rec):
    cells[(int(x * 100), int(y * 100))].append(i)

out = open(S + "/tr_station5.geojsonl", "w")
n = hit = 0
tot = 0
top = []
for l in open(S + "/tr_station4.geojsonl"):
    f = json.loads(l)
    x, y = f["geometry"]["coordinates"]
    nm = f["properties"]["n"]
    n += 1
    s = 0
    used = set()
    gx, gy = int(x * 100), int(y * 100)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for i in cells.get((gx + dx, gy + dy), ()):
                if i in used:
                    continue
                rn, rx, ry, rv, op = rec[i]
                if rn != nm:
                    continue
                if math.hypot((rx - x) * KX, (ry - y) * KY) > 1.5:   # 1.5km 以内算同一个駅
                    continue
                used.add(i)
                s += rv
    if s:
        hit += 1
        tot += s
        f["properties"]["pax"] = s
        top.append((s, nm))
    out.write(json.dumps(f, ensure_ascii=False) + "\n")
out.close()
top.sort(reverse=True)
print("合并后的駅 %d 个，配上客流的 %d（%.1f%%），合计 %.2f 亿人次/日"
      % (n, hit, 100 * hit / n, tot / 1e8))
print("前 12 名：")
for v, nm in top[:12]:
    print("   %-10s %9d" % (nm, v))
print("大阪几个：")
for want in ("梅田", "大阪", "難波", "天王寺", "鶴橋", "京橋", "新今宮"):
    for v, nm in top:
        if nm == want:
            print("   %-8s %9d" % (nm, v))
            break
