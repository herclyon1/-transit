#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""越南和缅甸下钻一级。

用户：「越南那边的我想细化一下地图，你能不能做到。缅甸那边呢？」「先只这两国细化」。

不用重新下载——`ea_all.pbf` 当初抽的时候 `boundary=administrative` 是整条留的，
只是后面只用了 admin_level 2/4，6 那一级一直躺在里面。

各自的「下一级」是什么，按各国**现行**制度定：

  越南  2025-07-01 的行政区划改革把 63 省并成 34 省，**并且撤掉了县级**，
        变成「省 → 社/坊」两级。所以下一级就是社/坊（xã / phường），
        OSM 里是 admin_level=6。实测抽到 **3,320 个**，官方 3,321，差 1 个。
        我们现有的省级正好是 34 个，也就是改革后的新版，对得上。

  缅甸  「省/邦 → 県(ခရိုင်) → 郡区(မြို့နယ်)」。取県一级 admin_level=6，
        实测 **121 个**——2022 年那次重组之后确实从 76 个增加到一百二十几个，
        不是抽多了。再往下的郡区（AL7，350 个）先不做。

名字：越南用越南语本名（拉丁），缅甸优先英文。不用中文——OSM 里越南的 name:zh 是喃字，
字库里没有，为它们生成字形要多十几个区段，纯浪费。实测这样一个新字形区段都不用加。
海岸线照样要裁——OSM 的行政界走的是领海线，不裁的话省界会泡在海里。
"""
import json, re, math, sys
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree
from shapely.ops import unary_union


def tags(s):
    d = {}
    if not s:
        return d
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"', s):
        d[m.group(1)] = m.group(2)
    return d


def rd(p):
    for l in open(p):
        s = l.replace("\x1e", "").strip()
        if s:
            yield json.loads(s)


# 父单元（34 越南省 + 17 缅甸省邦），用来判归属并继承 grp
units, props = [], []
for f in rd("/home/user/osm/units_osm2.geojsonl"):
    if f["properties"]["grp"] not in ("VNM", "MMR"):
        continue
    g = shape(f["geometry"])
    if not g.is_valid:
        g = g.buffer(0)
    units.append(g)
    props.append(f["properties"])
utree = STRtree(units)
print("父单元", len(units), flush=True)

# 陆地（东南亚范围）
land = []
for f in rd("/home/user/osm/sea_land.geojsonl") if False else []:
    pass
import subprocess
subprocess.run(["ogr2ogr", "-f", "GeoJSONSeq", "/home/user/osm/sea_land.geojsonl",
                "/home/user/osm/region_land.gpkg", "land",
                "-spat", "91", "8", "111", "29"], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for f in rd("/home/user/osm/sea_land.geojsonl"):
    g = shape(f["geometry"])
    if not g.is_valid:
        g = g.buffer(0)
    land.append(g)
ltree = STRtree(land)
print("陆地块", len(land), flush=True)

out = open("/home/user/osm/sub_units.geojsonl", "w")
pts = open("/home/user/osm/sub_pt.geojsonl", "w")
n = clipped = 0
stat = {}
for src, want in [("/home/user/osm/vn_sub.geojsonl", "VNM"),
                  ("/home/user/osm/mm_sub.geojsonl", "MMR")]:
    for f in rd(src):
        p = f["properties"]
        if p.get("admin_level") != "6":
            continue
        try:
            g = shape(f["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            rp = g.representative_point()
        except Exception:
            continue
        grp = None
        for i in utree.query(rp):
            if units[i].contains(rp):
                grp = props[i]["grp"]
                parent = props[i]["n"]
                break
        if grp != want:
            continue
        t = tags(p.get("other_tags"))
        # 名字：越南用越南语本名（拉丁字母）。**不能用 name:zh**——
        # OSM 里越南的 name:zh 是喃字（𠀧𡊤𣷷 这种），Noto Sans JP 根本没有这些字，
        # 为它们生成字形要多十几个区段，纯浪费。
        # 缅甸优先英文（Bago District 这种），没有才回退缅甸文。
        nm = (p.get("name") if want == "VNM"
              else (t.get("name:en") or t.get("name:zh-Hans") or p.get("name") or ""))
        if not nm:
            continue
        # 裁到陆地
        hit = ltree.query(g)
        if len(hit):
            try:
                c = unary_union([land[i] for i in hit]).intersection(g)
                if not c.is_empty and c.area > g.area * 0.2:
                    if c.area < g.area * 0.999:
                        clipped += 1
                    g = c
            except Exception:
                pass
        gj = mapping(g)
        if gj["type"] == "GeometryCollection":
            ps = [x for x in gj["geometries"] if "Polygon" in x["type"]]
            if not ps:
                continue
            co = []
            for x in ps:
                co.extend([x["coordinates"]] if x["type"] == "Polygon" else x["coordinates"])
            gj = {"type": "MultiPolygon", "coordinates": co}
        pr = {"n": nm, "grp": grp, "up": parent}
        out.write(json.dumps({"type": "Feature", "properties": pr, "geometry": gj},
                             ensure_ascii=False) + "\n")
        r = g.representative_point()
        pts.write(json.dumps({"type": "Feature", "properties": pr,
                              "geometry": {"type": "Point",
                                           "coordinates": [round(r.x, 6), round(r.y, 6)]}},
                             ensure_ascii=False) + "\n")
        n += 1
        stat[grp] = stat.get(grp, 0) + 1
out.close()
pts.close()
print("下一级单元 %d（%s），其中被海岸线裁过 %d" % (n, stat, clipped))
