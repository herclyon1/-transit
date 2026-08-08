#!/bin/bash
# 用 OSM 海岸线（官方每日构建的陆地多边形）裁剪行政区。
#
# 必须用 split 版：complete 版里整个欧亚大陆是一个多边形，上千万顶点，
# 拿一个省去跟它求交会慢到不可用（实测 12 个省要 2 分钟）。
#
# 正确性判据：内陆行政区面积必须分毫未变，只有沿海的会缩小。
set -eu
cd /home/user/osm

if [ ! -s region_land.gpkg ]; then
  echo "=== 裁出区域陆地块"
  ogr2ogr -f GPKG region_land.gpkg land-polygons-split-4326/land_polygons.shp \
    -spat 60 -15 180 56 -nln land -lco SPATIAL_INDEX=YES
fi
ogrinfo -so region_land.gpkg land | grep -i "feature count"

echo "=== 把行政区并进同一个库（跨库 join 用不了空间索引）"
ogr2ogr -f GPKG -update -append region_land.gpkg adm_raw.gpkg adm -nln adm -lco SPATIAL_INDEX=YES

echo "=== 空间索引连接求交"
time ogr2ogr -f GeoJSONSeq adm_clipped.geojsonl region_land.gpkg -dialect SQLITE -sql "
SELECT a.fid AS src_fid, a.name AS name, a.admin_level AS admin_level,
       a.other_tags AS other_tags,
       ST_Union(ST_Intersection(a.geom, l.geom)) AS geom
FROM adm a
JOIN rtree_land_geom r
  ON r.maxx >= ST_MinX(a.geom) AND r.minx <= ST_MaxX(a.geom)
 AND r.maxy >= ST_MinY(a.geom) AND r.miny <= ST_MaxY(a.geom)
JOIN land l ON l.fid = r.id
WHERE ST_Intersects(a.geom, l.geom)
GROUP BY a.fid"

echo "CLIP_DONE $(du -h adm_clipped.geojsonl | cut -f1)"
