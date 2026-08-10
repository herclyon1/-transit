#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把同一个市区町村里**同名的町丁合并成一个要素**。

用户报的：「有很多像图片这种，一个名字町，但是被切分出很多不同的区域，我不理解是为什么。」
截图里泉南市的「新家」出现 4 次、泉佐野市的「南中樫井」出现 2 次。

原因：e-Stat 的国勢調査小地域是按**調査区**切的，不是按町。一个大字人口多了
就会被拆成几个調査区，每个調査区一条记录。于是地图上同一个町被内部边界切开，
名字也重复标了好几遍。这是数据粒度问题，不是几何错。

修法：按 (県, 市区町村码, 町名) 合并——
  - 几何 unary_union：相邻的会真的粘成一块，内部那条线消失；
    本来就分离的（飞地、离岛）合成 MultiPolygon，还是分开画，但只有一个名字、一次高亮。
  - 人口/世帯相加，卡片显示的就是整个町的数。
  - 标注点一个町只出一个，放在最大的那个部件上。

无名的块不合并——没名字就没法判断是不是同一个町，合了反而制造出假的大块。

实测：231,677 条 → 207,730 个町（10,322 组被合并，最多的一组是
山口県山陽小野田市「大字小野田」的 62 块）。
"""
import json, collections
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

SRC = "/home/user/osm/ka_clip2.geojsonl"
KILL = set(json.load(open("/home/user/osm/cho_drop.json")))
OUT = "/home/user/osm/ka_merged.geojsonl"

groups = collections.OrderedDict()
solo = []
n = 0
with open(SRC) as f:
    for l in f:
        s = l.replace("\x1e", "").strip()
        if not s:
            continue
        ft = json.loads(s)
        p = ft["properties"]
        if p.pop("idx", None) in KILL:
            continue
        n += 1
        name = (p.get("n") or "").strip()
        if not name:
            solo.append(ft)
            continue
        k = (p.get("pref"), p.get("city"), name)
        groups.setdefault(k, []).append(ft)

multi = sum(1 for v in groups.values() if len(v) > 1)
print("输入 %d 条；有名字的分成 %d 组（其中 %d 组被拆成多块），无名 %d 条"
      % (n, len(groups), multi, len(solo)), flush=True)

out = open(OUT, "w")
m = fail = 0
for (pref, city, name), fts in groups.items():
    props = {"n": name, "city": city, "pref": pref,
             "pop": sum(int(x["properties"].get("pop") or 0) for x in fts),
             "hh": sum(int(x["properties"].get("hh") or 0) for x in fts)}
    if len(fts) == 1:
        g = fts[0]["geometry"]
    else:
        gs = []
        for x in fts:
            try:
                q = shape(x["geometry"])
                if not q.is_valid:
                    q = q.buffer(0)
                gs.append(q)
            except Exception:
                pass
        try:
            u = unary_union(gs)
            g = mapping(u)
        except Exception:
            fail += 1
            for x in fts:                       # 合不了就原样各写各的，绝不丢数据
                out.write(json.dumps(x, ensure_ascii=False) + "\n")
                m += 1
            continue
    out.write(json.dumps({"type": "Feature", "properties": props,
                          "geometry": g}, ensure_ascii=False) + "\n")
    m += 1
for x in solo:
    out.write(json.dumps(x, ensure_ascii=False) + "\n")
    m += 1
out.close()
print("写出 %d 个町丁（合并失败 %d 组，已原样保留）" % (m, fail))
