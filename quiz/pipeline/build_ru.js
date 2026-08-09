// 東亜视图里补上樺太（サハリン）与千島列島。
// 两者都是俄罗斯实控，按项目既定规则填俄罗斯的旗青色。
// 北方四岛已经在 disp 层单独画着（带虚线与说明），这里必须扣掉，否则同一块地画两遍
// ——README 里「同一块地只能有一个来源」那条红线。
"use strict";
const fs=require("fs");
const {area,bbox,repPoint,contains}=require("/home/user/osm/geo.js");
const D="/home/user/osm";
const polysOnly=g=>{if(!g)return null;if(g.type==="Polygon")return[g.coordinates];
  if(g.type==="MultiPolygon")return g.coordinates;return null;};

// 已经画在别处的：北海道（都道府県层）、北方四岛（disp 层）
const prefOrder=fs.readFileSync(D+"/jp_pref.geojsonl","utf8").split("\n").filter(Boolean).map(l=>JSON.parse(l).properties);
let hok=null;
for(const l of fs.readFileSync(D+"/jp_pref_clip.geojsonl","utf8").split("\n")){
  const s=l.replace(/^\x1e/,"").trim(); if(!s)continue; let f; try{f=JSON.parse(s)}catch(e){continue}
  const m=prefOrder[f.properties.uid-1]; if(!m||m.code!==1)continue;
  hok={type:"MultiPolygon",coordinates:polysOnly(f.geometry)};
}
const disp=JSON.parse(fs.readFileSync(D+"/jp_disp_fixed.geojsonl","utf8").split("\n")[0]).geometry;
const hbb=bbox(hok), dbb=bbox(disp);
const inside=(g,bb,pt)=>pt[0]>=bb[0]&&pt[0]<=bb[2]&&pt[1]>=bb[1]&&pt[1]<=bb[3]&&contains(g,pt);

const kar=[], kur=[];
let skipHok=0, skipDisp=0, skipKam=0, skipMain=0;
for(const l of fs.readFileSync(D+"/ru_raw.geojsonl","utf8").split("\n")){
  const s=l.replace(/^\x1e/,"").trim(); if(!s)continue; let f; try{f=JSON.parse(s)}catch(e){continue}
  for(const poly of polysOnly(f.geometry)||[]){
    const rp=repPoint({type:"Polygon",coordinates:poly}); if(!rp)continue;
    if(inside(hok,hbb,rp)){skipHok++;continue;}          // 北海道的属岛
    if(inside(disp,dbb,rp)){skipDisp++;continue;}        // 北方四岛，已在 disp 层
    // 樺太与千島以 145.2°E 分组（樺太最东 144.75°E，千島最西 145.5°E，中间没有陆地）。
    // 千島那组还必须卡纬度：抽取范围的东北角伸到了**堪察加半岛南端**
    // （ロパトカ岬 50.86°N/156.7°E），不卡的话千島会多出十倍面积。
    // 千島最北的阿頼度島 50.86°N、占守島 50.78°N，两者与堪察加隔第一千島海峡；
    // 用 50.95°N 切，正好落在海峡里，不切开任何岛。
    if(rp[0] < 145.2){
      // 抽取范围的西界还漏进了**大陆（ハバロフスク地方）**：间宮海峡最窄处
      // 大陆一直伸到 141.55°E，而樺太最西的ラッハ岬在 141.63°E。
      // 不切的话樺太会多出 3,456 km²。用 141.60°E 切，正好落在海峡里。
      if(rp[0] < 141.60){ skipMain++; }
      else kar.push(poly);
    }
    else if(rp[1] < 50.95){ kur.push(poly); }
    else { skipKam++; }
  }
}
const A=c=>Math.abs(area({type:"MultiPolygon",coordinates:c}))/1e6;
console.log("剔除：北海道属岛 %d 块、北方四岛 %d 块、堪察加 %d 块、大陆 %d 块", skipHok, skipDisp, skipKam, skipMain);
console.log("樺太 %d 块 %s km²（公开 76,400）", kar.length, A(kar).toFixed(0));
console.log("千島列島（北方四岛除外）%d 块 %s km²（千島全体约 10,500，减去四岛约 5,000 → 约 5,500）",
  kur.length, A(kur).toFixed(0));
const top=c=>c.map(p=>({a:Math.abs(area({type:"Polygon",coordinates:p}))/1e6,b:bbox({type:"Polygon",coordinates:p})}))
  .sort((x,y)=>y.a-x.a).slice(0,5);
console.log("  樺太最大 5 块:", top(kar).map(x=>x.a.toFixed(0)+"km²").join(" "));
console.log("  千島最大 5 块:", top(kur).map(x=>x.a.toFixed(0)+"km²@"+x.b[1].toFixed(1)+"N").join(" "),
  "（幌筵島 2053・得撫島 1450・温禰古丹島 425 が上位のはず）");

const out=fs.createWriteStream(D+"/ru_units.geojsonl");
const mk=(n,note,c)=>({type:"Feature",properties:{n,note,de_facto:"RUS"},
  geometry:{type:"MultiPolygon",coordinates:c}});
const f1=mk("樺太（サハリン）","ロシア連邦 サハリン州。1905-1945 は北緯50度以南が日本領（樺太庁）",kar);
const f2=mk("千島列島","ロシア連邦 サハリン州。北方四島は別途破線で表示",kur);
out.write(JSON.stringify(f1)+"\n"+JSON.stringify(f2)+"\n"); out.end();

const pt=fs.createWriteStream(D+"/ru_pt.geojsonl");
[[f1,kar],[f2,kur]].forEach(([f,c])=>{
  let best=null,ba=-1;
  for(const p of c){const a=Math.abs(area({type:"Polygon",coordinates:p})); if(a>ba){ba=a;best=p;}}
  const rp=repPoint({type:"Polygon",coordinates:best});
  pt.write(JSON.stringify({type:"Feature",properties:{n:f.properties.n},geometry:{type:"Point",coordinates:rp}})+"\n");
});
pt.end();
console.log("标注点已生成");
