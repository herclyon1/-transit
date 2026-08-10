#!/bin/bash
# 東亜交通瓦片。切到 z11——再往下没意义：日本境内有 N02 那份更准的，
# 别国 OSM 本身也没有更细的分类。
#
# 铁路**按类拆成四个 source-layer**，不是塞一层再靠 filter 分。理由是分级：
#   一层的话，z3 那张瓦片里必须装下全部 96,581 条高铁 + 253,268 条普铁，
#   实测 z3 一屏渲染 47,174 条线，手机上必卡。拆开之后 z3 的瓦片里只有高铁，
#   普铁从 z5、地铁/轻轨从 z8 才进瓦片，低缩放的瓦片自然就小了。
# 另外铁路只留 k 一个属性（不带线长），这样 --coalesce 才能把同属性的相邻
# 线段合并——OSM 的一条干线被切成上千段 way，合并之后要素数掉一个量级。
set -eu
D=/home/user/osm
cd $D

python3 - <<'PY'
import json
o = {k: open("/home/user/osm/ea_rail_%s.geojsonl" % k, "w")
     for k in ("hs", "rail", "sub", "lrt")}
n = {k: 0 for k in o}
for l in open("/home/user/osm/ea_rail.geojsonl"):
    f = json.loads(l)
    k = f["properties"]["k"]
    f["properties"] = {}          # 属性全去掉，让 --coalesce 能合并
    o[k].write(json.dumps(f, ensure_ascii=False) + "\n")
    n[k] += 1
for f in o.values():
    f.close()
print("铁路分层:", n)
PY

tippecanoe -o eatr.pmtiles -f -Z2 -z11 \
  --simplify-only-low-zooms --coalesce \
  --drop-densest-as-needed --extend-zooms-if-still-dropping -q \
  -L'{"file":"ea_rail_hs.geojsonl","layer":"railhs","minzoom":3}' \
  -L'{"file":"ea_rail_rail.geojsonl","layer":"rail","minzoom":5}' \
  -L'{"file":"ea_rail_sub.geojsonl","layer":"railsub","minzoom":8}' \
  -L'{"file":"ea_rail_lrt.geojsonl","layer":"raillrt","minzoom":8}' \
  -L'{"file":"ea_ferry.geojsonl","layer":"ferry","minzoom":3}' \
  -L'{"file":"ea_air.geojsonl","layer":"air","minzoom":7}' \
  -L'{"file":"ea_airpt.geojsonl","layer":"airpt","minzoom":3}' \
  -L'{"file":"ea_port.geojsonl","layer":"port","minzoom":5}' \
  -L'{"file":"ea_bc.geojsonl","layer":"bc","minzoom":5}'
ls -l eatr.pmtiles | awk '{printf "eatr.pmtiles %.1f MB%s\n", $5/1048576, ($5>100*1024*1024?"  !! 超 GitHub 单文件 100MB":"")}'
