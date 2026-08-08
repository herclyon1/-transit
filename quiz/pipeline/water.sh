#!/bin/bash
# 从同一份合并文件里抽水体和河流。
#
# 关键：水体/河流必须和边界来自**同一个 OSM 快照**。
# 旧数据的病根就是国界来自 CGAZ、河流来自另一处，两边各自简化过，
# 于是中朝边界和鸭绿江永远差一点。现在它们本来就是同一批 way。
#
# 河流只在 z6 以上绘制（见 tiles.sh）：低层级下河流看不清，
# 而分图层各自简化有可能让边界和河流微微分叉，索性回避。
set -eu
cd /home/user/osm

echo "=== 湖泊/水库（面）"
rm -f water_raw.geojsonl
ogr2ogr -f GeoJSONSeq water_raw.geojsonl ea_all.pbf multipolygons \
  -where "natural='water' OR landuse='reservoir'" -progress

echo "=== 河流（线）"
rm -f rivers_raw.geojsonl
ogr2ogr -f GeoJSONSeq rivers_raw.geojsonl ea_all.pbf lines \
  -where "waterway IN ('river','riverbank')" -progress

wc -l water_raw.geojsonl rivers_raw.geojsonl
echo "WATER_DONE"
