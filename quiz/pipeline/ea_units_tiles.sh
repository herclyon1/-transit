#!/bin/bash
# 東亜行政区瓦片（一级单元 + 争议区 + 越南/缅甸的下一级）。
# 之前也是手敲的，没落成文件。
#
# 参数陷阱（本项目已踩）：--simplification=N 是**倍率**，2 表示简化力度加倍；
# 想保精度不是把它调小，而是 --simplify-only-low-zooms 让最高层级完全不简化。
# --no-simplification-of-shared-nodes 保住相邻多边形的共享顶点，这是不出缝的关键。
set -eu
D=/home/user/osm
cd $D

tippecanoe -o ea_units.pmtiles -f -Z0 -z12 -r1 \
  --simplify-only-low-zooms \
  --no-simplification-of-shared-nodes \
  --detect-shared-borders \
  --no-tile-size-limit -q \
  -L'{"file":"units_osm3.geojsonl","layer":"units"}' \
  -L'{"file":"ea_unit_pt3.geojsonl","layer":"unitlab"}' \
  -L'{"file":"disp_osm.geojsonl","layer":"disp"}' \
  -L'{"file":"ea_disp_pt.geojsonl","layer":"displab"}' \
  -L'{"file":"sub_units.geojsonl","layer":"sub","minzoom":6}' \
  -L'{"file":"sub_pt.geojsonl","layer":"sublab","minzoom":6}'
ls -l ea_units.pmtiles | awk '{printf "ea_units.pmtiles %.1f MB%s\n", $5/1048576, ($5>100*1024*1024?"  !! 超 GitHub 单文件 100MB":"")}'
