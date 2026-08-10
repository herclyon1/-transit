#!/bin/bash
# 日本の公共交通瓦片（国土数値情報 N02 鉄道 / C28 空港 / OSM route=ferry / S12 乗降客数）。
# 之前这一份是手敲 tippecanoe 跑的，没落成文件，用户说过「这种东西你做完就丢吗，吓人」。
set -eu
S=/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad
cd /home/user/osm

tippecanoe -o transit.pmtiles -f -Z4 -z14 -r1 \
  --drop-densest-as-needed --extend-zooms-if-still-dropping \
  --no-tile-size-limit -q \
  -L'{"file":"'$S'/tr_rail.geojsonl","layer":"rail"}' \
  -L'{"file":"'$S'/tr_ferry3.geojsonl","layer":"ferry"}' \
  -L'{"file":"'$S'/tr_air3.geojsonl","layer":"air"}' \
  -L'{"file":"'$S'/tr_airlab.geojsonl","layer":"airlab"}' \
  -L'{"file":"'$S'/tr_station_p.geojsonl","layer":"station"}' \
  -L'{"file":"'$S'/tr_stationseg2.geojsonl","layer":"stationseg"}'
ls -l transit.pmtiles | awk '{printf "transit.pmtiles %.1f MB\n", $5/1048576}'
