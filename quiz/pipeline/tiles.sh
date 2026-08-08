#!/bin/bash
# 切矢量瓦片，拆成两个文件绕开 GitHub 单文件 100MB 上限。
#
# 参数陷阱（本项目已踩）：--simplification=N 是**倍率**，2 表示简化力度加倍。
# 想保精度不是把它调小，而是用 --simplify-only-low-zooms 让最高层级完全不简化。
# --no-simplification-of-shared-nodes 保住相邻多边形的共享顶点，这是不出缝的关键。
set -eu
cd /home/user/osm

echo "=== 边界层（精度优先）"
tippecanoe -o ea_units.pmtiles -f -Z0 -z12 \
  --simplify-only-low-zooms \
  --no-simplification-of-shared-nodes \
  --detect-shared-borders \
  --no-tile-size-limit -q \
  -L units:units_osm.geojsonl \
  -L disp:disp_osm.geojsonl
echo "units: $(du -h ea_units.pmtiles|cut -f1)"

echo "=== 水体河流层（体积优先）"
tippecanoe -o ea_water.pmtiles -f -Z0 -z12 \
  --drop-densest-as-needed --extend-zooms-if-still-dropping \
  --no-tile-size-limit -q \
  -L'{"file":"water_osm.geojsonl","layer":"water","minzoom":3}' \
  -L'{"file":"rivers_osm.geojsonl","layer":"rivers","minzoom":5}'
echo "water: $(du -h ea_water.pmtiles|cut -f1)"

echo "TILES_DONE"
for f in ea_units.pmtiles ea_water.pmtiles; do
  ls -l $f | awk '{ if ($5 > 100*1024*1024) print "  !! 超 100MB:", $9, $5; else print "  OK:", $9, $5 }'
done
