#!/bin/bash
# 探测每个提取包里，各 admin_level 上带 ISO3166-2 的关系数量，按国家前缀分组。
# 目的：用实测数据决定每个国家该取哪一级，而不是拍脑袋猜。
cd /home/user/osm
for f in *.osm.pbf; do
  case "$f" in bnd_*|coast.*|wtr_*) continue;; esac
  echo "### $f"
  osmium tags-filter -R "$f" r/boundary=administrative -f opl 2>/dev/null | node -e '
  let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{
    const m={};
    for(const l of d.split("\n")){
      if(l[0]!=="r") continue;
      const t=(l.match(/ T(.*?)( M|$)/)||[])[1]||"";
      const al=(t.match(/(?:^|,)admin_level=([^,]*)/)||[])[1];
      if(!al||!/^\d+$/.test(al)) continue;
      const iso=(t.match(/(?:^|,)ISO3166-2=([^,]*)/)||[])[1];
      if(!iso) continue;
      const cc=iso.split("-")[0];
      (m[cc]=m[cc]||{})[al]=(m[cc][al]||0)+1;
    }
    Object.keys(m).sort().forEach(cc=>{
      const s=Object.keys(m[cc]).sort((a,b)=>a-b).map(k=>"AL"+k+":"+m[cc][k]).join("  ");
      console.log("   "+cc.padEnd(4)+s);
    });
  });'
done
echo "PROBE_DONE"
