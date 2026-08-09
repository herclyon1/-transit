# -*- coding: utf-8 -*-
"""从 e-Stat 町丁溶合出市町村层。
   起因：用户点泉佐野市的飞地「大口新田」，卡片写对了泉佐野市，**高亮却框不住它**。
   根子在于市町村几何来自 OSM、町丁来自 e-Stat，两份数据在 607 处不一致——
   拿 OSM 的泉佐野市去描边，本来就不包含 e-Stat 认为属于它的那块飞地。
   这不是显示 bug，是两层用了两个来源。
   修法：市町村层改成**由町丁溶合而来**，从此上下两级几何必然自洽。
   市町村这级 2018-10-01 之后没有过合并，所以令和2年的边界就是现行边界，不存在时效问题。
"""
import json, collections
mc = json.load(open("/home/user/osm/mcodes.json"))
name_of = {}
for c, n in mc["muni"].items(): name_of[c] = n
for c, v in mc["ku"].items():   name_of[c] = v["shi"]     # 区码归到母市

out = open("/home/user/osm/muni_src.geojsonl", "w", encoding="utf-8")
n = 0; miss = collections.Counter()
with open("/home/user/osm/ka_all.geojsonl") as f:
    for l in f:
        ft = json.loads(l); p = ft["properties"]
        c = p.get("city"); pr = p.get("pref")
        if not c or pr is None: continue
        code = "%02d%03d" % (pr, int(c))
        nm = name_of.get(code)
        if not nm: miss[code] += 1; continue
        out.write(json.dumps({"type":"Feature",
            "properties":{"key": "%02d|%s" % (pr, nm), "n": nm, "pref": pr},
            "geometry": ft["geometry"]}, ensure_ascii=False) + "\n")
        n += 1
out.close()
print("待溶合町丁", n, "，查不到市町村名而丢弃", sum(miss.values()), dict(list(miss.items())[:5]))
