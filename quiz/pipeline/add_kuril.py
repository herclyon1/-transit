#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补上北方領土（及樺太・千島）的水体、河川、空港。

用户报的：「北方領土缺失了水体和交通元素。」

为什么原来没有：東亜那批 OSM 提取包是按 21 个国家/地区下的，**不含俄罗斯**。
北方四島在 OSM 里属于俄罗斯，所以它们的湖泊、河流、机场一个都没抓到。
（現代日本视图更彻底——它压根没挂水体层，琵琶湖霞ヶ浦也都被県的填色盖着，
  那条已在 map.html 里单独修了。）

补法：另下 Geofabrik 的 russia/far-eastern-fed-district（367MB），
按 140.5–157.5E / 42.5–55.5N 抽水体和河川，合并进 water_cov / rivers_cov。
顺带把岛上的三个机场也抽出来加进交通层。

铁路和轮渡：**这两样是真没有**，不是漏抓。
千島列島全域没有任何铁路（OSM 里 railway=rail 在该范围为空，现实中也从未修过）；
定期航路是俄方的（コルサコフ〜南クリル），不在国土数値情報 N09 里，
所以交通图层里这两类在北方領土上仍然是空的——这是事实，不是缺数据。
"""
import json, re, math

SCRATCH = "/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad"
SKIP_WATER = {"bay", "lagoon", "strait", "cove", "harbour"}


def tags(s):
    d = {}
    if not s:
        return d
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"', s):
        d[m.group(1)] = m.group(2)
    return d


def ring_area(r):
    a = 0.0
    for i in range(len(r) - 1):
        x1, y1 = r[i]
        x2, y2 = r[i + 1]
        a += math.radians(x2 - x1) * (2 + math.sin(math.radians(y1)) + math.sin(math.radians(y2)))
    return abs(a * 6378137.0 * 6378137.0 / 2.0)


def km2(g):
    if g["type"] == "Polygon":
        return ring_area(g["coordinates"][0]) / 1e6
    return sum(ring_area(p[0]) for p in g["coordinates"]) / 1e6


def name_of(p, t):
    return t.get("name:ja") or t.get("name:zh-Hans") or t.get("name:en") or p.get("name") or ""


# ── 水体 ──
n = 0
with open("/home/user/osm/water_ru.geojsonl", "w") as o:
    for l in open("/home/user/osm/ru_water_raw.geojsonl"):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        f = json.loads(s)
        t = tags(f["properties"].get("other_tags"))
        if t.get("water") in SKIP_WATER:
            continue
        o.write(json.dumps({"type": "Feature",
                            "properties": {"n": name_of(f["properties"], t),
                                           "a": int(round(km2(f["geometry"])))},
                            "geometry": f["geometry"]}, ensure_ascii=False) + "\n")
        n += 1
print("俄方水体", n)

# ── 河川 ──
m = 0
with open("/home/user/osm/rivers_ru.geojsonl", "w") as o:
    for l in open("/home/user/osm/ru_riv_raw.geojsonl"):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        f = json.loads(s)
        t = tags(f["properties"].get("other_tags"))
        o.write(json.dumps({"type": "Feature",
                            "properties": {"n": name_of(f["properties"], t)},
                            "geometry": f["geometry"]}, ensure_ascii=False) + "\n")
        m += 1
print("俄方河川", m)

# ── 空港（只取北方四島范围内、有名字的）──
k = 0
with open(SCRATCH + "/tr_air_ru.geojsonl", "w") as o:
    for l in open("/home/user/osm/ru_air_raw.geojsonl"):
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        f = json.loads(s)
        t = tags(f["properties"].get("other_tags"))
        nm = t.get("name:ja") or t.get("name:en") or f["properties"].get("name")
        if not nm:
            continue                      # 无名的跑道不画，不编造
        o.write(json.dumps({"type": "Feature",
                            "properties": {"n": nm, "kind": "ru", "t": 9},
                            "geometry": f["geometry"]}, ensure_ascii=False) + "\n")
        k += 1
        print("   空港", nm)
print("北方領土 空港", k)
