#!/bin/bash
# 逐个提取包按标签瘦身，只保留边界/海岸线/水体/河流及其引用对象。
# 之后合并成一个区域文件再组装关系——否则跨境关系会被切断，单元被静默丢弃。
set -u
cd /home/user/osm
mkdir -p filt
f="$1"
n=$(basename "$f" .osm.pbf)
[ -s "filt/$n.pbf" ] && { echo "SKIP $n"; exit 0; }
osmium tags-filter "$f" \
  r/boundary=administrative \
  w/boundary=administrative \
  w/natural=coastline \
  w/waterway=river,riverbank \
  r/waterway=river \
  w/natural=water \
  r/natural=water \
  w/landuse=reservoir \
  r/landuse=reservoir \
  -o "filt/$n.part.pbf" --overwrite \
  && mv "filt/$n.part.pbf" "filt/$n.pbf" \
  && echo "OK $n $(du -h filt/$n.pbf | cut -f1)" \
  || echo "FAIL $n"
