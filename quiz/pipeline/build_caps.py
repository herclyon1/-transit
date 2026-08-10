#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一级行政区的标注点搬到它自己的首府/県庁所在地上，顺带给出首府城市点。

用户报的：「东亚那边的一级行政区的名字能不能标在各自省会上，你看这新疆的名字
都标到哪儿去了。这引出一个新元素就是把各自省会城市能不能标出来。现代日本地图
那边也要标。你看这京都府兵库县都到哪里去了。」

原来标注点是多边形的代表点。对新疆、京都府、兵庫県这种细长或形状怪的单元，
代表点会落在离任何城市都很远的地方。改成放在首府上，一个点同时干两件事：
上方写行政区名，下方写首府名，中间一个圆点就是首府位置。

首府怎么来的：
  日本  —— pref 层本来就带 `cap`（県庁所在地名）。拿这个名字去 OSM 的 place 节点里
           找同名的 city/town，取它的坐标。这是城市中心点，不是市域代表点。
  東亜  —— OSM 的 place 节点带 `capital` 标签，级别语义是
           yes/2 = 国都、3 = 次级、4 = 一级行政区首府、5/6 = 更低。
           按 4 → 3 → 2/yes → 5 → 6 → 该单元内人口最多的 city → town 逐级回退，
           取落在该单元多边形内部的那个。
找不到的单元保留原来的代表点，并且 cap 留空——渲染时就不画圆点也不写首府名，
不编造。
"""
import json, re, collections, sys
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

PLACES = "/home/user/osm/places.geojsonl"


def tags(s):
    d = {}
    if not s:
        return d
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"', s):
        d[m.group(1)] = m.group(2)
    return d


print("载入 place 节点…", flush=True)
places = []
for l in open(PLACES):
    s = l.replace("\x1e", "").strip()
    if not s:
        continue
    f = json.loads(s)
    p = f["properties"]
    t = tags(p.get("other_tags"))
    pl = p.get("place")
    if pl not in ("city", "town", "village", "municipality"):
        continue
    try:
        pop = int(re.sub(r"[^0-9]", "", t.get("population", "") or "0") or 0)
    except Exception:
        pop = 0
    places.append({
        "xy": f["geometry"]["coordinates"],
        "name": p.get("name") or "",
        "ja": t.get("name:ja") or "",
        "zh": (t.get("name:zh-Hans") or t.get("name:zh") or "").split(" / ")[0],
        "en": t.get("name:en") or "",
        "cap": t.get("capital"),
        "place": pl,
        "pop": pop,
    })
print("place 节点", len(places), flush=True)

pts = [Point(*p["xy"]) for p in places]
ptree = STRtree(pts)

# 首府优先级：一级行政区首府 > 次级 > 国都 > 更低 > 大城市
RANK = {"4": 0, "3": 1, "2": 2, "yes": 2, "5": 3, "6": 4}


def pick(poly):
    """在多边形里挑一个最像首府的 place 节点。"""
    best = None
    for i in ptree.query(poly):
        if not poly.contains(pts[i]):
            continue
        p = places[i]
        r = RANK.get(p["cap"], 5 if p["place"] == "city" else 6)
        key = (r, -p["pop"])
        if best is None or key < best[0]:
            best = (key, p)
    return best[1] if best else None


def run(src, out, namekey, capkey):
    o = open(out, "w")
    n = hit = 0
    for l in open(src):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        f = json.loads(s)
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        n += 1
        pr = dict(f["properties"])
        c = pick(g)
        if capkey and pr.get(capkey):
            # 日本：県庁所在地的名字是已知的，直接按名字找，不猜
            want = re.sub(r"[（(].*", "", pr[capkey]).strip()
            c = None
            for i in ptree.query(g):
                if not g.contains(pts[i]):
                    continue
                p = places[i]
                if want in (p["ja"], p["name"]):
                    if c is None or p["place"] == "city":
                        c = p
        if c:
            xy = c["xy"]
            # 首府名优先中文，其次日文，再其次英文——最后才用当地文字。
            # 字形只生成了标注实际用到的区段，泰文/老挝文/高棉文/迪维希文
            # 这些区段是为这批名字才补上的（build_glyphs 里列了）。
            pr["cap"] = pr.get(capkey) or c["zh"] or c["ja"] or c["en"] or c["name"]
            hit += 1
        else:
            xy = list(g.representative_point().coords)[0]
            pr["cap"] = ""
        o.write(json.dumps({"type": "Feature", "properties": pr,
                            "geometry": {"type": "Point", "coordinates": [xy[0], xy[1]]}},
                           ensure_ascii=False) + "\n")
    o.close()
    print("%s: %d 个单元，定位到首府 %d（%.1f%%）" % (out, n, hit, 100 * hit / n))


run("/home/user/osm/jp_pref_final.geojsonl", "/home/user/osm/jp_pref_pt2.geojsonl", "n", "cap")
run("/home/user/osm/units_osm.geojsonl", "/home/user/osm/ea_unit_pt2.geojsonl", "n", None)
