#!/bin/bash
# 切矢量瓦片。
#
# 陷阱：tippecanoe 按层级做的简化，和当年 mapshaper `interval` 毁掉边界精度是同一类问题。
# 对策：--simplification 调小；--detect-shared-borders 让相邻多边形共用边简化一致，避免出缝；
# 河流从 z5 起才画（低层级看不清，且分图层各自简化可能让边界与河流微微分叉）。
# 切完必须逐级量段长验收，不能切完就当完事。
set -eu
cd /home/user/osm
OUT=${1:-ea.pmtiles}
tippecanoe -o "$OUT" -f -Z0 -z12 \
  --detect-shared-borders --simplification=2 \
  --drop-densest-as-needed --extend-zooms-if-still-dropping --no-tile-size-limit -q \
  -L units:units_osm.geojsonl \
  -L disp:disp_osm.geojsonl \
  -L'{"file":"water_osm.geojsonl","layer":"water","minzoom":3}' \
  -L'{"file":"rivers_osm.geojsonl","layer":"rivers","minzoom":5}'
echo "TILES_DONE $(du -h "$OUT" | cut -f1)"
ls -l "$OUT" | awk '{ if ($5 > 100*1024*1024) print "  !! 超过 GitHub 单文件 100MB 上限:", $5; else print "  体积 OK:", $5 }'
