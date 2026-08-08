#!/bin/bash
# 从合并后的区域文件里抽行政区多边形。
# 必须在合并文件上做——按国家单独抽会切断跨境关系，静默丢单元（平安北道就是这么丢的）。
set -eu
cd /home/user/osm

echo "=== 抽 admin_level 2..6 的行政区多边形"
ogr2ogr -f GPKG adm_raw.gpkg ea_all.pbf multipolygons \
  -where "boundary='administrative' AND admin_level IN ('2','3','4','5','6')" \
  -nln adm -lco SPATIAL_INDEX=YES -progress

echo "=== 结果统计"
ogrinfo -q -dialect SQLITE -sql \
  "SELECT admin_level, COUNT(*) AS n FROM adm GROUP BY admin_level ORDER BY admin_level" adm_raw.gpkg

echo "EXTRACT_DONE"
