#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""市町村层跟官方名单对齐，修三处。

拿国土地理院《面積調》的名单逐県核对，全国 47 県只有 4 处对不上：
  01 北海道 少 5 个村（留別・留夜別・紗那・蘂取・色丹，加上跟古宇郡重名的国後郡泊村共 6 个）
     —— 这是北方領土的 6 村，按「填色按实际管理走」的既定规则本来就不进市町村层，
        它们画在 disp 层（虚线范围 + 说明）。不是错，不动。
  12 千葉県 多一个「所属未定地」—— 0.08 km²，在葛西沖，是境界未定地不是市町村，
     混在市町村层里会让计数变成 1741 却少一个真市。删掉。
  21 岐阜県 我们写「飛驒市」，官方写「飛騨市」—— e-Stat 那边也是「飛騨市」，
     两处不一致会让町丁级和市町村级对不上名字。按官方统一成「飛騨市」。
  25 滋賀県 整个「米原市」不见了 —— 不是过滤掉的，是 OSM 那份 pbf 里
     米原市的 admin_level=7 关系本身就建不出多边形（GDAL 报了上千个几何错误）。
     250 km²、3.7 万人的市在地图上是个洞。
     补法：用它自己的 97 个町丁（e-Stat 25214，已裁到陆地）合并出边界。
     实测合出来 250.58 km²，官方 250.39，差 +0.08%，单一多边形不碎。
     两家来源拼接会有毫米级错位，实测：跟彦根市重叠 0.31、長浜市 0.13、多賀町 0.06 km²，
     越出滋賀県界 0.10 km²，滋賀県内总空隙 0.39 km²——都在 0.1% 量级，任何缩放下都看不见。
"""
import json, math
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

SRC = "/home/user/osm/jp_muni_final.geojsonl"
OUT = "/home/user/osm/jp_muni_final2.geojsonl"
PTS = "/home/user/osm/jp_muni_pt.geojsonl"
PTO = "/home/user/osm/jp_muni_pt2.geojsonl"


def km2(g):
    lat = (g.bounds[1] + g.bounds[3]) / 2
    return g.area * (111.32 ** 2) * math.cos(math.radians(lat))


# 1) 从町丁合出米原市
parts = []
with open("/home/user/osm/ka_clip2.geojsonl") as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        p = ft["properties"]
        if p.get("pref") == 25 and p.get("city") == "214":
            g = shape(ft["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            parts.append(g)
print("米原市 町丁 %d 块" % len(parts))
mai = unary_union(parts)
if mai.geom_type == "Polygon":
    mai = shape({"type": "MultiPolygon", "coordinates": [mapping(mai)["coordinates"]]})
print("合并后 %.2f km²（官方 250.39），部件 %d" % (km2(mai), len(mai.geoms)))

o = open(OUT, "w")
n = drop = ren = 0
with open(SRC) as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        p = ft["properties"]
        if p["n"] == "所属未定地":
            drop += 1
            continue
        if p["n"] == "飛驒市":
            p["n"] = "飛騨市"
            p["zh"] = "飛騨市"
            ren += 1
        o.write(json.dumps(ft, ensure_ascii=False) + "\n")
        n += 1
o.write(json.dumps({"type": "Feature",
                    "properties": {"n": "米原市", "zh": "米原市", "pref": 25, "prefn": "滋賀県"},
                    "geometry": mapping(mai)}, ensure_ascii=False) + "\n")
n += 1
o.close()
print("市町村 %d（删所属未定地 %d，改名 %d，补米原市 1）" % (n, drop, ren))

# 2) 标注点同步
rp = mai.representative_point()
o = open(PTO, "w")
m = 0
with open(PTS) as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        if ft["properties"]["n"] == "所属未定地":
            continue
        if ft["properties"]["n"] == "飛驒市":
            ft["properties"]["n"] = "飛騨市"
        o.write(json.dumps(ft, ensure_ascii=False) + "\n")
        m += 1
o.write(json.dumps({"type": "Feature", "properties": {"n": "米原市", "pref": 25},
                    "geometry": {"type": "Point", "coordinates": [rp.x, rp.y]}},
                   ensure_ascii=False) + "\n")
m += 1
o.close()
print("市町村标注点", m)
