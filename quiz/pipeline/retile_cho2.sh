#!/bin/bash
# 用裁剪后的町丁重切瓦片。
#   输入 ka_merged.geojsonl —— clip2.py 裁到陆地 → water_rule.py 删 15 块港内残骸
#   → merge_cho.py 把同一市区町村里同名的町丁合并成一个要素（231,677 → 207,959）
# 面数据仍按地方切 4 份：单份 z14 会超 GitHub 100MB 单文件上限。
set -e
D=/home/user/osm
cd $D
node --max-old-space-size=6000 -e '
const fs=require("fs"),readline=require("readline"),{area,repPoint}=require("/home/user/osm/geo.js");
const G={a:[1,7],b:[8,23],c:[24,39],d:[40,47]};
const outs={},n={};
for(const k of Object.keys(G)){outs[k]=fs.createWriteStream(`/home/user/osm/kc_${k}.geojsonl`);n[k]=0;}
const lab=fs.createWriteStream("/home/user/osm/cho_pt2.geojsonl");
const polysOnly=g=>{if(!g)return null;if(/Polygon/.test(g.type))return g;if(g.type!=="GeometryCollection")return null;
  const ps=[];g.geometries.forEach(x=>{if(x.type==="Polygon")ps.push(x.coordinates);else if(x.type==="MultiPolygon")ps.push(...x.coordinates);});
  return ps.length?{type:"MultiPolygon",coordinates:ps}:null;};
let tot=0,lb=0;
readline.createInterface({input:fs.createReadStream("/home/user/osm/ka_merged.geojsonl")}).on("line",l=>{
  const s=l.replace(/^\x1e/,"").trim(); if(!s)return; let f; try{f=JSON.parse(s)}catch(e){return}
  const p=f.properties;
  for(const k of Object.keys(G)) if(p.pref>=G[k][0]&&p.pref<=G[k][1]){outs[k].write(JSON.stringify(f)+"\n");n[k]++;break;}
  tot++;
  let g=polysOnly(f.geometry); if(!g||!p.n)return;
  if(g.type==="MultiPolygon"&&g.coordinates.length>1){       // 标注点放在最大的那个部件上
    let b=null,ba=-1;
    for(const q of g.coordinates){const x=Math.abs(area({type:"Polygon",coordinates:q}));if(x>ba){ba=x;b=q;}}
    g={type:"Polygon",coordinates:b};}
  const rp=repPoint(g); if(!rp)return;
  lab.write(JSON.stringify({type:"Feature",properties:{n:p.n},geometry:{type:"Point",coordinates:rp}})+"\n");lb++;
}).on("close",()=>{
  for(const k of Object.keys(G))outs[k].end();
  lab.end();
  console.log("町丁 "+tot+"，标注点 "+lb);
  console.log("分组 "+JSON.stringify(n));
});
'
for K in a b c d; do
  tippecanoe -o $D/ka_${K}_new.pmtiles -f -Z8 -z14 -r1 \
    --simplify-only-low-zooms --no-simplification-of-shared-nodes \
    --drop-densest-as-needed --extend-zooms-if-still-dropping \
    -L cho:$D/kc_${K}.geojsonl 2>&1 | tr "\r" "\n" | tail -1
  echo "ka_$K done: $(du -h $D/ka_${K}_new.pmtiles | cut -f1)"
done
tippecanoe -o $D/cholab_new.pmtiles -f -Z10 -z14 -r1 --drop-densest-as-needed \
  --extend-zooms-if-still-dropping -L cholab:$D/cho_pt2.geojsonl 2>&1 | tr "\r" "\n" | tail -1
echo RETILEDONE
ls -la $D/ka_?_new.pmtiles $D/cholab_new.pmtiles
