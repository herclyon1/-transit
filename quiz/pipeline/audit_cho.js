// 把 23 万个町丁的代表点逐个丢进 OSM 市町村多边形，看 e-Stat 的 CITY 码和 OSM 的市界是否一致。
// 用户在真机上点出「大口新田」被标成泉南市（实为泉佐野市的飞地），要求系统性排查。
"use strict";
const fs=require("fs"), readline=require("readline");
const {contains,bbox,repPoint,area}=require("/home/user/osm/geo.js");
const D="/home/user/osm";
const MC=JSON.parse(fs.readFileSync(D+"/mcodes.json","utf8"));
const names=MC.muni, kuTbl=MC.ku;
// 政令市の区：e-Stat 给的是区码（大阪市北区 27127），而 OSM 的 muni 层是「大阪市」。
// 这不是错，是两边粒度不同，比对时归一化到母市。
const expect=code=>kuTbl[code]?kuTbl[code].shi:names[code];

const munis=[];
fs.readFileSync(D+"/jp_muni_final.geojsonl","utf8").split("\n").filter(Boolean).forEach(l=>{
  const f=JSON.parse(l); munis.push({n:f.properties.n,pref:f.properties.pref,g:f.geometry,bb:bbox(f.geometry)});});
console.error("OSM 市町村",munis.length);

// 0.1 度网格索引
const G=10, grid=new Map();
const gk=(x,y)=>Math.floor(x*G)+","+Math.floor(y*G);
munis.forEach((m,i)=>{
  for(let x=Math.floor(m.bb[0]*G);x<=Math.floor(m.bb[2]*G);x++)
    for(let y=Math.floor(m.bb[1]*G);y<=Math.floor(m.bb[3]*G);y++){
      const k=x+","+y; if(!grid.has(k))grid.set(k,[]); grid.get(k).push(i);}
});
console.error("网格格子",grid.size);

let n=0,noHit=0,ok=0;
const bad=new Map();
const rl=readline.createInterface({input:fs.createReadStream(D+"/ka_all.geojsonl"),crlfDelay:Infinity});
rl.on("line",l=>{
  if(!l.trim())return; let f; try{f=JSON.parse(l);}catch(e){return;}
  const p=f.properties; if(!p.city||p.pref==null)return;
  const rp=repPoint(f.geometry); if(!rp)return;
  n++;
  const code=String(p.pref).padStart(2,"0")+String(p.city).padStart(3,"0");
  const want=expect(code);
  const cand=grid.get(gk(rp[0],rp[1]))||[];
  let got=null;
  for(const i of cand){const m=munis[i];
    if(rp[0]<m.bb[0]||rp[0]>m.bb[2]||rp[1]<m.bb[1]||rp[1]>m.bb[3])continue;
    if(contains(m.g,rp)){got=m;break;}}
  if(!got){noHit++;return;}
  if(want && got.n===want){ok++;return;}
  const key=code+" "+(want||"?")+" → OSM:"+got.n;
  if(!bad.has(key))bad.set(key,{c:0,ex:[]});
  const b=bad.get(key); b.c++; if(b.ex.length<3)b.ex.push(p.n);
});
rl.on("close",()=>{
  console.log("町丁总数 %d，命中 OSM 市町村 %d，落在所有市町村之外 %d",n,n-noHit,noHit);
  console.log("与 e-Stat 的 CITY 码一致 %d（%s%%），不一致 %d",ok,(100*ok/(n-noHit)).toFixed(3),(n-noHit-ok));
  const arr=[...bad.entries()].sort((a,b)=>b[1].c-a[1].c);
  console.log("不一致的组合共 %d 种：",arr.length);
  arr.forEach(([k,v])=>console.log("  %s  ×%d   例：%s",k,v.c,v.ex.join("、")));
});
