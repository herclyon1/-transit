#!/bin/bash
cd /home/user/osm
R="asia/china asia/india asia/japan asia/indonesia asia/philippines asia/thailand asia/vietnam asia/myanmar asia/malaysia-singapore-brunei asia/bangladesh asia/nepal asia/sri-lanka asia/taiwan asia/south-korea asia/mongolia asia/cambodia asia/laos asia/bhutan asia/maldives asia/east-timor australia-oceania"
for r in $R; do
  n=$(basename $r)
  [ -s "$n.osm.pbf" ] && { echo "SKIP $n"; continue; }
  echo "GET $n ..."
  curl -sSL --retry 4 --retry-delay 3 -o "$n.osm.pbf.part" "https://download.geofabrik.de/$r-latest.osm.pbf" \
    && mv "$n.osm.pbf.part" "$n.osm.pbf" && echo "OK $n $(du -h $n.osm.pbf|cut -f1)" || echo "FAIL $n"
done
echo "ALL_DONE total=$(du -sh /home/user/osm|cut -f1)"
