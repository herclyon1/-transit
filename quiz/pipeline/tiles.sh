#!/bin/bash
# 切矢量瓦片。
#
# 陷阱警告：tippecanoe 按缩放级别做的简化，跟当年 mapshaper `interval` 毁掉
# 边界精度是同一类问题。`interval` 是面积阈值不是段长阈值，误解那一点把中蒙国界
# 从 91m 削到了 1469m。这里的对策：
#   1. --simplification 调小，高层级基本不简化
#   2. --detect-shared-borders 让相邻多边形共用的边简化方式一致，避免出现缝
#   3. 切完必须跑 verify_tiles.js 逐级量段长，不能切完就当完事
set -eu
cd /home/user/osm

OUT=${1:-ea.pmtiles}

tippecanoe -o "$OUT" -f \
  -Z0 -z12 \
  --detect-shared-borders \
  --simplification=2 \
  --drop-densest-as-needed \
  --extend-zooms-if-still-dropping \
  --no-tile-size-limit \
  -L units:units_osm.geojsonl \
  -L water:water_osm.geojsonl \
  -L rivers:rivers_osm.geojsonl

echo "TILES_DONE $(du -h "$OUT" | cut -f1)"
echo
echo "GitHub 单文件上限 100MB —— 超了就得砍图层或砍缩放级别，别硬传。"
ls -l "$OUT" | awk '{ if ($5 > 100*1024*1024) print "  !! 超限:", $5, "字节"; else print "  体积 OK:", $5, "字节" }'
