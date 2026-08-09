#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""町丁字里的「水面調査区」剔除规则（裁剪之后的收尾）。

背景：e-Stat 的国勢調査小地域是**調査区**不是行政界，里面混着水面調査区
（港湾水域、湖面、河口）。它们没有人口没有世帯，几何一直铺到海里，
用户点船橋市/川崎区的町丁会亮到海面上。

主力方案是 clip2.py 的几何裁剪（裁到 OSM 陆地多边形上），
对国土地理院官方面積調，±2% 达标率 88.7% → 96.7%。
但裁完还剩一类去不掉的：港内的防波堤、栈桥、护岸——OSM 把这些算陆地，
所以「水面」这种整块水域的調査区裁完还剩个几平方公里的骨架，
川崎区就还剩 6.69 km²，比官方数字高 16.6%。

这个脚本负责收尾。两条死路先说在前面：
  1. 拿名字当判据（水面|水域|港湾|湾$|港$…）——「港」「湾」是常见地名用字，
     会把山形県小国町、長野県飯島町/上松町/南箕輪村这些内陆山村删残。
  2. 一刀切删掉所有名字带「水面/水域」的块——東京都中央区那块叫「水面調査区」的
     裁完剩 1.37 km² 其实是晴海一带的实地，删了反而从 -0.9% 掉到 -12.5%。

所以名字只当**候选**，判据是两条守卫：
  候选 = 人口0 且 世帯0 且（无名 或 名字含水域用字）
  守卫 = 只有当该市区町村的町丁面积总和超过官方面積調 2% 时才动手，
         且每删一块都必须让该市区町村的绝对误差变小，删到进 ±2% 就停手。
两条都是可证明的：本来达标的一块不动，动了的每一步都离官方数字更近。

基准数据：国土地理院《全国都道府県市区町村別面積調》令和8年4月1日（含政令市の区）。
"""
import json, re, collections, sys

CHO = sys.argv[1] if len(sys.argv) > 1 else "/home/user/osm/cho_tbl2.tsv"
MEN = json.load(open("/home/user/osm/mencho.json"))

WATER = re.compile(r"水面|水域|港|湾|沖|地先|埋立|埋め立て")
UP = 1.02

rows = []
with open(CHO) as f:
    for line in f:
        i, pref, city, name, pop, hh, ar = line.rstrip("\n").split("\t")
        rows.append((int(i), int(pref), city, name, int(pop), int(hh), float(ar)))

by = collections.defaultdict(list)
for r in rows:
    by["%02d%s" % (r[1], r[2])].append(r)


def cand(r):
    return r[4] == 0 and r[5] == 0 and (r[3].strip() == "" or WATER.search(r[3]))


def report(drop, tag):
    d = set(drop)
    n = i1 = i2 = i5 = 0
    res = {}
    for code, rs in by.items():
        m = MEN.get(code)
        if not m:
            continue
        t = m["area"]
        n += 1
        a = sum(r[6] for r in rs if r[0] not in d)
        e = abs(a - t) / t
        res[code] = e
        if e <= .01: i1 += 1
        if e <= .02: i2 += 1
        if e <= .05: i5 += 1
    print("[%s] 删 %d 块 %.1f km²  可比 %d  ≤1%% %d(%.1f%%)  ≤2%% %d(%.1f%%)  ≤5%% %d(%.1f%%)"
          % (tag, len(d), sum(r[6] for r in rows if r[0] in d), n,
             i1, 100 * i1 / n, i2, 100 * i2 / n, i5, 100 * i5 / n))
    return res


base = report([], "裁剪后")

drop, touched = [], []
for code, rs in by.items():
    m = MEN.get(code)
    if not m:
        continue
    t = m["area"]
    a = sum(r[6] for r in rs)
    if a <= t * UP:
        continue
    for c in sorted([r for r in rs if cand(r)], key=lambda r: -r[6]):
        if a <= t * UP:
            break
        if abs(a - c[6] - t) >= abs(a - t):
            continue
        drop.append(c[0])
        a -= c[6]
        touched.append((code, m["name"], c[3], c[6]))

after = report(drop, "收尾后")
worse = [c for c in base if after[c] > .02 >= base[c]]
print("本来达标、删后反而不达标:", len(worse))
for c in worse[:20]:
    print("   %s %s  %.1f%% → %.1f%%" % (c, MEN[c]["name"], base[c] * 100, after[c] * 100))

print("\n涉及 %d 个市区町村，删块（按面积）:" % len(set(x[0] for x in touched)))
for code, mnm, n, a in sorted(touched, key=lambda x: -x[3]):
    print("   %s %-16s %-22s %8.2f km²" % (code, mnm, n or "(无名)", a))

json.dump(drop, open("/home/user/osm/cho_drop.json", "w"))
print("\n写出 cho_drop.json:", len(drop))
