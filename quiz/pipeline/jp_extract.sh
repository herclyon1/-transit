#!/bin/bash
# 抽日本的都道府県(AL4)与市町村(AL7)。
# 注意：GDAL 的 OSM 驱动的 -where 不支持 ST_MinX 之类的空间函数，范围过滤只能用 -spat。
set -eu
cd /home/user/osm
rm -f jp_raw.geojsonl
ogr2ogr -f GeoJSONSeq jp_raw.geojsonl ea_all.pbf multipolygons \
  -spat 122 23 155 47 \
  -where "boundary='administrative' AND admin_level IN ('4','7')" \
  -progress
echo "JP_DONE $(grep -c '' jp_raw.geojsonl)"
