#!/bin/bash
# 東亜交通 第二遍下载：补**车站**（第一遍漏了，用户报「火车站你都不标么，存在重大缺陷」）。
#
# 为什么非得重下：第一遍的 osmium tags-filter 只留了 railway=rail 那几个**线**的标签，
# railway=station 是打在**点**（有时是面）上的，在抽取那一步就被扔了，
# eatr/*.pbf 里根本没有。原始包当时因为磁盘只剩 6GB 已经删掉了，只能重下。
#
# 这一遍顺手把以后可能要的也一起留下，免得再来第三遍：
#   车站   railway=station,halt（点/面/关系）+ 站前广场那种 public_transport=station
#   高速   highway=motorway,trunk（用户说「高速公路的等我后面考虑一下」，
#          先存着不画，真要画的时候不用再下 15GB）
set -u
cd /home/user/osm
mkdir -p eatr2
R="asia/china asia/india asia/indonesia asia/philippines asia/thailand asia/vietnam asia/myanmar asia/malaysia-singapore-brunei asia/bangladesh asia/nepal asia/sri-lanka asia/taiwan asia/south-korea asia/north-korea asia/mongolia asia/cambodia asia/laos asia/bhutan asia/maldives asia/east-timor australia-oceania"
export OPENSSL_CONF=/tmp/claude-0/-home-user--transit/6dea591c-e942-5ede-824a-c8008ae45b5c/scratchpad/ossl.cnf
for r in $R; do
  n=$(basename $r)
  [ -s "eatr2/$n.pbf" ] && { echo "SKIP $n"; continue; }
  echo "GET $n ..."
  curl -sSL --retry 4 --retry-delay 3 --cacert /root/.ccr/ca-bundle.crt \
    -o "_dl2.pbf" "https://download.geofabrik.de/$r-latest.osm.pbf" || { echo "FAIL_DL $n"; continue; }
  osmium tags-filter _dl2.pbf \
    n/railway=station,halt w/railway=station,halt r/railway=station,halt \
    n/public_transport=station w/public_transport=station \
    w/highway=motorway,trunk \
    -o "eatr2/$n.pbf" --overwrite 2>/dev/null \
    && echo "OK $n $(du -h eatr2/$n.pbf|cut -f1)" || echo "FAIL_FILT $n"
  rm -f _dl2.pbf
  df -h /home/user | tail -1
done
echo EATR_DL2_DONE
du -sh /home/user/osm/eatr2
