#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补上马尼拉大都会，并把被它顶掉名字的奎松省改回来。

自查东亚各国首都的时候发现的：**马尼拉市中心一屏没有任何行政区底面**——
`ea-fill` 在 120.98,14.60 查不到要素，等于地图上马尼拉是个洞。

原因：菲律宾的一级行政区我们按默认取 `admin_level=4`（省），
而**马尼拉大都会（NCR）在 OSM 里是 AL3**，它下面直接是市、没有省，
于是 AL4 在那一块什么都没有 → 一个洞。

连带第二个错：`select_units.js` 按名字把旧数据的单元对到 OSM 候选上，
「马尼拉大都会」这个名字被安到了一块 AL4 的多边形上——
那块的范围是 121.24–122.79E / 13.16–15.22N，183 个部件，是**奎松省**。
也就是说图上奎松省一直顶着「马尼拉大都会」的名字。

修法：
  1. 从 OSM 取 AL3 的 Metro Manila（面积 0.0761°²，含市中心），裁到陆地，
     作为新的一级单元加进去，grp=PHL。
  2. 把那块 AL4 的多边形改回它自己的名字（按 OSM 里同一块地的 AL4 单元定名）。
  3. 首府点：马尼拉市（AL6 Manila 的代表点）。

奎松省的名字从 OSM 的 name:zh 取；OSM 给的是「奎松省」。
"""
import json, re, math, subprocess, os
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

D = "/home/user/osm"
PT = Point(120.98, 14.60)          # 马尼拉市中心


def tags(s):
    d = {}
    if s:
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"', s):
            d[m.group(1)] = m.group(2)
    return d


def rd(p):
    for l in open(p, errors="replace"):
        s = l.replace("\x1e", "").strip()
        if s:
            try:
                yield json.loads(s)
            except Exception:
                pass


# OSM 没给 name:zh 的，按通用译名补上。整份数据里其余菲律宾省名都是中文，
# 只有这一个会突然变成英文。
ZH_FIX = {"Quezon": "奎松省"}


def zh(t, fallback=""):
    """OSM 的 name:zh 常写成「简体;繁体」或「简体 / 繁体」，取前一段。"""
    v = t.get("name:zh") or t.get("name:zh-Hans") or ""
    v = re.split(r"[;/]", v)[0].strip()
    v = v or fallback
    return ZH_FIX.get(v, v)


# ── 1) 从 OSM 拿 Metro Manila（AL3）和各 AL4 省 ──
ncr = None
al4 = []
for f in rd(D + "/_phadm.geojsonl"):
    p = f["properties"]
    t = tags(p.get("other_tags"))
    t.update({k: v for k, v in p.items() if k != "other_tags" and v})
    al = str(t.get("admin_level") or "")
    if al not in ("3", "4"):
        continue
    try:
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
    except Exception:
        continue
    nm = zh(t, p.get("name") or "")
    if al == "3" and g.contains(PT):
        if ncr is None or g.area < ncr[1].area:      # 取最小的那个＝NCR 本身
            ncr = (nm, g)
    elif al == "4":
        al4.append((nm, g))
if not ncr:
    raise SystemExit("没找到 AL3 的 Metro Manila")
print("NCR：%s 面积 %.4f°²" % (ncr[0], ncr[1].area))

# ── 2) 裁到陆地（OSM 的行政界走领海线，不裁会泡在海里）──
subprocess.run(["ogr2ogr", "-f", "GeoJSONSeq", D + "/_phland.geojsonl",
                D + "/region_land.gpkg", "land", "-spat", "120.5", "14.2", "121.4", "15.0"],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
land = []
for f in rd(D + "/_phland.geojsonl"):
    g = shape(f["geometry"])
    land.append(g if g.is_valid else g.buffer(0))
os.remove(D + "/_phland.geojsonl")
g = ncr[1]
if land:
    c = unary_union(land).intersection(g)
    if not c.is_empty and c.area > g.area * 0.5:
        print("  裁到陆地：%.4f → %.4f°²" % (g.area, c.area))
        g = c
ncr_geom = g

# ── 3) 改写 units_osm2：给错名的那块改回真名，末尾追加 NCR ──
src = D + "/units_osm2.geojsonl"
dst = D + "/units_osm3.geojsonl"
o = open(dst, "w")
n = fixed = 0
for f in rd(src):
    p = f["properties"]
    if p.get("grp") == "PHL" and p.get("n") == "马尼拉大都会":
        try:
            gg = shape(f["geometry"])
            rp = gg.representative_point()
        except Exception:
            rp = None
        real = None
        if rp is not None:
            best = None
            for nm, q in al4:
                if q.contains(rp):
                    if best is None or q.area < best[1].area:
                        best = (nm, q)
            real = best[0] if best else None
        if real and real != "马尼拉大都会":
            print("  改名：马尼拉大都会 → %s（范围 %s）"
                  % (real, [round(v, 2) for v in gg.bounds]))
            p["n"] = real
            f["properties"] = p
            fixed += 1
    o.write(json.dumps(f, ensure_ascii=False) + "\n")
    n += 1

gj = mapping(ncr_geom)
if gj["type"] == "GeometryCollection":
    ps = [x for x in gj["geometries"] if "Polygon" in x["type"]]
    co = []
    for x in ps:
        co.extend([x["coordinates"]] if x["type"] == "Polygon" else x["coordinates"])
    gj = {"type": "MultiPolygon", "coordinates": co}
o.write(json.dumps({"type": "Feature",
                    "properties": {"grp": "PHL", "n": "马尼拉大都会", "src": "osm",
                                   "cap": "马尼拉"},
                    "geometry": gj}, ensure_ascii=False) + "\n")
o.close()
print("单元 %d → %d（改名 %d，新增 马尼拉大都会 1）" % (n, n + 1, fixed))

# ── 4) 标注点：马尼拉市自己的位置 ──
mp = None
for f in rd(D + "/_phadm.geojsonl"):
    p = f["properties"]
    t = tags(p.get("other_tags"))
    t.update({k: v for k, v in p.items() if k != "other_tags" and v})
    if str(t.get("admin_level") or "") != "6" or (p.get("name") or "") != "Manila":
        continue
    try:
        g = shape(f["geometry"])
        mp = g.representative_point()
    except Exception:
        pass
    break
if mp is None:
    mp = ncr_geom.representative_point()

src = D + "/ea_unit_pt2.geojsonl"
dst = D + "/ea_unit_pt3.geojsonl"
o = open(dst, "w")
k = 0
for f in rd(src):
    p = f["properties"]
    if p.get("grp") == "PHL" and p.get("n") == "马尼拉大都会":
        continue                     # 旧的那个点在奎松省，扔掉
    o.write(json.dumps(f, ensure_ascii=False) + "\n")
    k += 1
o.write(json.dumps({"type": "Feature",
                    "properties": {"grp": "PHL", "n": "马尼拉大都会", "cap": "马尼拉"},
                    "geometry": {"type": "Point",
                                 "coordinates": [round(mp.x, 6), round(mp.y, 6)]}},
                   ensure_ascii=False) + "\n")
o.close()
print("标注点 %d → %d，马尼拉大都会 的点放在 %.4f,%.4f" % (k, k + 1, mp.x, mp.y))

# ── 5) 复查 ──
cover = []
for f in rd(dst.replace("ea_unit_pt3", "units_osm3")):
    p = f["properties"]
    if p.get("grp") != "PHL":
        continue
    try:
        if shape(f["geometry"]).contains(PT):
            cover.append(p["n"])
    except Exception:
        pass
print("复查：覆盖马尼拉市中心的单元 =", cover)
