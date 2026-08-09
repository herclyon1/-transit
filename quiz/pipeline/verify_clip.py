#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""裁剪结果的三道验收。任何一道不过就别往瓦片里放。
  1. 有人口的町丁不许消失，也不许被裁掉一大半（上一版就是栽在这，相原町直接没了）
  2. 全国 1,741 个市町村的面积必须比裁之前更接近 OSM 实测市界
  3. 逐个列出裁后反而更离谱的市町村
"""
import json, collections, sys

mn = json.load(open("/home/user/-transit/quiz/muni_names.json"))
osm = json.load(open("/home/user/osm/osm_muni_area.json"))
rows = {}
for line in open("/home/user/osm/cho_tbl.tsv"):
    i, pref, city, name, pop, hh, ar = line.rstrip("\n").split("\t")
    rows[int(i)] = (int(pref), city, name, int(pop), int(hh), float(ar))

st = {}
for l in open("/home/user/osm/clip2_stat.tsv"):
    k, tag, a0, a1 = l.rstrip("\n").split("\t")
    st[int(k)] = (tag, float(a0), float(a1))

by = collections.defaultdict(lambda: [0.0, 0.0])
gone, shrunk = [], []
for k, (tag, a0, a1) in st.items():
    r = rows[k]
    f = (a1 / a0) if a0 > 0 else 0.0
    nm = mn.get("%02d%s" % (r[0], r[1]))
    if nm:
        by[(r[0], nm)][0] += r[5]
        by[(r[0], nm)][1] += r[5] * f
    if r[3] > 0:
        if f == 0:
            gone.append((r, tag))
        elif f < 0.6:
            shrunk.append((f, r))

print("① 有人口却被裁没的町丁: %d" % len(gone))
for r, t in gone[:15]:
    print("     %02d%s %-12s pop%6d %7.3f km²  %s" % (r[0], r[1], r[2], r[3], r[5], t))
print("① 有人口且缩水 >40%% 的町丁: %d（合计人口 %d）" %
      (len(shrunk), sum(r[3] for f, r in shrunk)))
for f, r in sorted(shrunk)[:20]:
    print("     保留%.2f %02d%s %-10s %-14s pop%6d %7.3f km²" %
          (f, r[0], r[1], mn.get("%02d%s" % (r[0], r[1]), "?"), r[2], r[3], r[5]))

n = i0 = i1 = 0
worse, better = [], []
for k, (a, b) in by.items():
    t = osm.get("%d|%s" % k)
    if not t:
        continue
    n += 1
    e0, e1 = abs(a - t) / t, abs(b - t) / t
    if e0 <= .02: i0 += 1
    if e1 <= .02: i1 += 1
    if e1 > e0 + .005: worse.append((e1 - e0, k, a, b, t))
    elif e0 > e1 + .005: better.append((e0 - e1, k, a, b, t))
print("\n② 可比市町村 %d：±2%% 内 %d(%.1f%%) → %d(%.1f%%)" %
      (n, i0, 100 * i0 / n, i1, 100 * i1 / n))
print("③ 裁后更准 %d 个，裁后更差 %d 个" % (len(better), len(worse)))
worse.sort(reverse=True)
for d, k, a, b, t in worse[:25]:
    print("     %d|%-10s %8.2f → %8.2f  OSM %8.2f  (%+.1f%% → %+.1f%%)" %
          (k[0], k[1], a, b, t, (a - t) / t * 100, (b - t) / t * 100))
