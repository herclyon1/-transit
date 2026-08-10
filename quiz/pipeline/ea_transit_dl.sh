#!/bin/bash
# 東亜交通：逐个国家 下载 → 抽标签 → 立刻删原始包。
#
# 为什么要重下：当初 filter.sh 只留了边界/海岸线/水体，交通被扔干净了。
# 为什么要一个一个来：这台机器只剩 6GB 空余，21 个包加起来 15GB，
#                     只能下一个抽一个删一个，峰值就是最大那个包（约 1.6GB）。
#
# 抽这几类（用户点的名）：
#   铁路   railway=rail/subway/light_rail/monorail/narrow_gauge + route=train/subway
#   机场   aeroway=aerodrome（点/线/关系都要，国际与否靠 aerodrome:type / iata 区分）
#   轮渡   route=ferry（真实航迹，不是直线）
#   港口   harbour=yes / industrial=port / seamark:type=harbour / amenity=ferry_terminal
#   口岸   barrier=border_control
set -u
cd /home/user/osm
mkdir -p eatr
R="asia/china asia/india asia/indonesia asia/philippines asia/thailand asia/vietnam asia/myanmar asia/malaysia-singapore-brunei asia/bangladesh asia/nepal asia/sri-lanka asia/taiwan asia/south-korea asia/mongolia asia/cambodia asia/laos asia/bhutan asia/maldives asia/east-timor australia-oceania"
export OPENSSL_CONF=/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad/ossl.cnf
for r in $R; do
  n=$(basename $r)
  [ -s "eatr/$n.pbf" ] && { echo "SKIP $n"; continue; }
  echo "GET $n ..."
  curl -sSL --retry 4 --retry-delay 3 --cacert /root/.ccr/ca-bundle.crt \
    -o "_dl.pbf" "https://download.geofabrik.de/$r-latest.osm.pbf" || { echo "FAIL_DL $n"; continue; }
  osmium tags-filter _dl.pbf \
    w/railway=rail,subway,light_rail,monorail,narrow_gauge \
    r/route=train,subway,light_rail,monorail \
    n/aeroway=aerodrome w/aeroway=aerodrome r/aeroway=aerodrome \
    w/route=ferry r/route=ferry \
    n/amenity=ferry_terminal w/amenity=ferry_terminal \
    n/harbour=yes w/harbour=yes r/harbour=yes \
    w/industrial=port n/seamark:type=harbour w/seamark:type=harbour \
    n/barrier=border_control w/barrier=border_control \
    -o "eatr/$n.pbf" --overwrite 2>/dev/null \
    && echo "OK $n $(du -h eatr/$n.pbf|cut -f1)" || echo "FAIL_FILT $n"
  rm -f _dl.pbf
  df -h /home/user | tail -1
done
echo EATR_DL_DONE
du -sh /home/user/osm/eatr
