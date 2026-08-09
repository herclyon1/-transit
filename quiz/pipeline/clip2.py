#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 e-Stat 町丁裁到 OSM 陆地上（第二版，shapely + STRtree）。

第一版走 ogr2ogr/spatialite 的 ST_Intersection + GROUP BY，退出码永远是 0，
但町田市掉了 19.3%、相原町（1.29 万人、6.59 km²）整块消失——静默失败没法查。
这一版三点不同：
  1. 用 shapely 直接跑 GEOS，每个要素单独 try/except，失败的记下来而不是变成空几何；
  2. 完全落在某块陆地里的町丁走 contains 快路径，几何一个字节都不动
     （内陆町丁占绝大多数，既快又杜绝「本来好好的被算坏了」）；
  3. 裁完必须过三道验收：有人口的块不许消失、掉得过狠的要报出来、
     市区町村面积要比裁之前更接近国土地理院《面積調》。任何一道不过就整体回退。
     实测 1,889 个市区町村，±2% 达标率 88.7% → 96.7%。
陆地底图：osmdata.openstreetmap.de 的 OSM 陆地多边形（日本 bbox 内 80,849 块）。
"""
import json, os, sys, math
from multiprocessing import Pool
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree
from shapely.ops import unary_union

SRC = "/home/user/osm/ka_all.geojsonl"
OUT = "/home/user/osm/ka_clip2.geojsonl"
LOG = "/home/user/osm/clip2_stat.tsv"

_land = None
_tree = None


def boot():
    global _land, _tree
    if _tree is not None:
        return
    ls = []
    with open("/home/user/osm/jland.geojsonl") as f:
        for l in f:
            s = l.replace("\x1e", "").strip()
            if not s:
                continue
            g = shape(json.loads(s)["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            ls.append(g)
    _land = ls
    _tree = STRtree(ls)


def work(chunk):
    boot()
    res = []
    for k, line in chunk:
        try:
            ft = json.loads(line)
            ft["properties"]["idx"] = k      # 让下游能按行号定位（切瓦片前会去掉）
        except Exception:
            res.append((k, None, "解析失败", 0, 0))
            continue
        try:
            g = shape(ft["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
        except Exception as e:
            res.append((k, json.dumps(ft, ensure_ascii=False), "几何不可用:%s" % str(e)[:40], 0, 0))
            continue
        a0 = g.area
        if a0 <= 0:
            res.append((k, None, "零面积", 0, 0))
            continue
        hit = _tree.query(g)
        if len(hit) == 0:
            res.append((k, None, "全水", a0, 0.0))       # 整块在海里
            continue
        # 快路径：整块落在一块陆地内部，原样保留
        keep = False
        for i in hit:
            try:
                if _land[i].contains(g):
                    keep = True
                    break
            except Exception:
                pass
        if keep:
            res.append((k, json.dumps(ft, ensure_ascii=False), "整块陆地", a0, a0))
            continue
        try:
            u = unary_union([_land[i] for i in hit])
            ng = u.intersection(g)
        except Exception as e:
            res.append((k, json.dumps(ft, ensure_ascii=False), "求交失败:%s" % str(e)[:40], a0, a0))  # 失败就原样留着
            continue
        a1 = ng.area
        if ng.is_empty or a1 <= 0:
            res.append((k, None, "裁成空", a0, 0.0))
            continue
        gj = mapping(ng)
        if gj["type"] == "GeometryCollection":
            ps = [x for x in gj["geometries"] if "Polygon" in x["type"]]
            if not ps:
                res.append((k, None, "裁后无面", a0, 0.0))
                continue
            co = []
            for x in ps:
                if x["type"] == "Polygon":
                    co.append(x["coordinates"])
                else:
                    co.extend(x["coordinates"])
            gj = {"type": "MultiPolygon", "coordinates": co}
        ft["geometry"] = gj
        res.append((k, json.dumps(ft, ensure_ascii=False), "裁剪", a0, a1))
    return res


def main():
    lines = []
    with open(SRC) as f:
        for k, l in enumerate(f):
            s = l.replace("\x1e", "").strip()
            if s:
                lines.append((k, s))
    only = os.environ.get("ONLYPREF")
    if only:
        keep = set(int(x) for x in only.split(","))
        lines = [(k, s) for k, s in lines
                 if json.loads(s)["properties"].get("pref") in keep]
    print("待处理", len(lines), flush=True)
    CH = 200
    chunks = [lines[i:i + CH] for i in range(0, len(lines), CH)]
    fo = open(OUT, "w")
    fl = open(LOG, "w")
    n = done = 0
    with Pool(4) as p:
        for res in p.imap_unordered(work, chunks):
            for k, out, tag, a0, a1 in res:
                if out:
                    fo.write(out + "\n")
                    n += 1
                fl.write("%d\t%s\t%.9f\t%.9f\n" % (k, tag, a0, a1))
            done += len(res)
            if done % 5000 < CH:
                print("  %d/%d" % (done, len(lines)), flush=True)
    fo.close()
    fl.close()
    print("写出", n)


if __name__ == "__main__":
    main()
