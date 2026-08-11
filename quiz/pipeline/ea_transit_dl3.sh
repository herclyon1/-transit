#!/bin/bash
# 東亜交通 第三遍下载：在建铁路、独立的长途汽车站、有轨电车。
#
# 用户：「长途汽车站可以保留啊，这个是细节补充，我只是希望能有标签名字而已。
#         然后在建铁路可以画啊，标注出来就行。」
#
# 为什么又要下：这三类当初在 osmium tags-filter 那一步就被扔了，包里没有——
#   railway=construction   第一遍只留了 railway=rail,subway,light_rail,monorail,narrow_gauge
#   amenity=bus_station    第二遍只靠 public_transport=station 捎带到了一部分，
#                          只打 amenity=bus_station 的（很常见）一个没留
#   railway=tram           顺手补上，图例里「軌道」本来就该包含有轨电车
# 顺带把 funicular（缆索铁路）也留下，同属轨道。
set -u
cd /home/user/osm
mkdir -p eatr3
R="asia/china asia/india asia/indonesia asia/philippines asia/thailand asia/vietnam asia/myanmar asia/malaysia-singapore-brunei asia/bangladesh asia/nepal asia/sri-lanka asia/taiwan asia/south-korea asia/north-korea asia/mongolia asia/cambodia asia/laos asia/bhutan asia/maldives asia/east-timor australia-oceania"
export OPENSSL_CONF=/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad/ossl.cnf
for r in $R; do
  n=$(basename $r)
  [ -s "eatr3/$n.pbf" ] && { echo "SKIP $n"; continue; }
  echo "GET $n ..."
  curl -sSL --retry 4 --retry-delay 3 --cacert /root/.ccr/ca-bundle.crt \
    -o "_dl3.pbf" "https://download.geofabrik.de/$r-latest.osm.pbf" || { echo "FAIL_DL $n"; continue; }
  osmium tags-filter _dl3.pbf \
    w/railway=construction,tram,funicular \
    n/railway=construction,tram_stop,halt w/railway=construction \
    n/amenity=bus_station w/amenity=bus_station r/amenity=bus_station \
    n/aerialway=station w/aerialway=station \
    -o "eatr3/$n.pbf" --overwrite 2>/dev/null \
    && echo "OK $n $(du -h eatr3/$n.pbf|cut -f1)" || echo "FAIL_FILT $n"
  rm -f _dl3.pbf
  df -h /home/user | tail -1
done
echo EATR_DL3_DONE
du -sh /home/user/osm/eatr3
