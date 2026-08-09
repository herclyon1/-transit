#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拿国土地理院《全国都道府県市区町村別面積調》当基准，逐个市区町村核町丁面积。

之前拿 OSM 市界当基准是有问题的：OSM 的市界把港湾水域也圈了进去，
川崎市 OSM 149.4 km²、官方只有 144.35 km²。所以「删掉港内水面块」在
市町村一级看是变差，在区一级看却是变好——基准本身不对。
这个脚本直接对官方数字，而且官方表连政令市の区都给了，能一路核到区。

用法: python3 verify_area.py <町丁面积表.tsv> [另一张表.tsv ...]
"""
import json, sys, collections

MEN = json.load(open("/home/user/osm/mencho.json"))


def load(p):
    by = collections.defaultdict(float)
    for line in open(p):
        i, pref, city, name, pop, hh, ar = line.rstrip("\n").split("\t")
        by["%02d%s" % (int(pref), city)] += float(ar)
    return by


def rep(by, tag, drop=None):
    n = i1 = i2 = i5 = i10 = 0
    bad = []
    for code, a in by.items():
        m = MEN.get(code)
        if not m:
            continue
        t = m["area"]
        n += 1
        e = abs(a - t) / t
        if e <= .01: i1 += 1
        if e <= .02: i2 += 1
        if e <= .05: i5 += 1
        if e <= .10: i10 += 1
        bad.append((e, code, m["name"], a, t))
    print("[%s] 可比市区町村 %d  ≤1%% %d(%.1f%%)  ≤2%% %d(%.1f%%)  ≤5%% %d(%.1f%%)  ≤10%% %d(%.1f%%)"
          % (tag, n, i1, 100 * i1 / n, i2, 100 * i2 / n, i5, 100 * i5 / n, i10, 100 * i10 / n))
    bad.sort(reverse=True)
    return {c: e for e, c, nm, a, t in bad}, bad


if __name__ == "__main__":
    prev = None
    for p in sys.argv[1:]:
        by = load(p)
        cur, bad = rep(by, p.split("/")[-1])
        if prev is not None:
            w = [c for c in prev if cur.get(c, 0) > .02 >= prev[c]]
            print("     本来 ±2%% 内、这一版掉出去的: %d" % len(w))
            for c in w[:15]:
                print("        %s %s  %.1f%% → %.1f%%" %
                      (c, MEN[c]["name"], prev[c] * 100, cur[c] * 100))
        prev = cur
    print("\n偏差最大的 25 个:")
    for e, c, nm, a, t in bad[:25]:
        print("   %s %-16s %9.2f vs 官方 %9.2f  (%+7.1f%%) %s" %
              (c, nm, a, t, (a - t) / t * 100, MEN[c]["note"]))
