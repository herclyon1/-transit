// 新增的标注点层：政令市の行政区（171）、町丁・字等（23 万）、修正后的北方領土。
const fs=require("fs"), readline=require("readline");
const {repPoint,area}=require("./geo.js");
const polysOnly=g=>{if(!g)return null;if(/Polygon/.test(g.type))return g;if(g.type!=="GeometryCollection")return null;
  const ps=[];g.geometries.forEach(s=>{if(s.type==="Polygon")ps.push(s.coordinates);else if(s.type==="MultiPolygon")ps.push(...s.coordinates);});
  return ps.length?{type:"MultiPolygon",coordinates:ps}:null;};
function build(src,out,pick,done){
  const w=fs.createWriteStream(out); let n=0,skip=0;
  const rl=readline.createInterface({input:fs.createReadStream(src),crlfDelay:Infinity});
  rl.on("line",l=>{const s=l.replace(/^\x1e/,"").trim(); if(!s)return;
    let f; try{f=JSON.parse(s)}catch(e){return}
    let g=polysOnly(f.geometry); if(!g){skip++;return;}
    if(g.type==="MultiPolygon"&&g.coordinates.length>1){
      let best=null,ba=-1;
      for(const p of g.coordinates){const a=Math.abs(area({type:"Polygon",coordinates:p})); if(a>ba){ba=a;best=p;}}
      g={type:"Polygon",coordinates:best};
    }
    const rp=repPoint(g); if(!rp){skip++;return;}
    const props=pick(f.properties); if(!props){skip++;return;}
    w.write(JSON.stringify({type:"Feature",properties:props,geometry:{type:"Point",coordinates:rp}})+"\n");
    n++;});
  rl.on("close",()=>{w.end();console.log(out,n,"跳过",skip);done&&done();});
}
build("jp_ku_clip.geojsonl","jp_ku_pt.geojsonl",p=>({n:p.n,shi:p.shi,pref:p.pref}),()=>
build("jp_disp_fixed.geojsonl","jp_disp_pt.geojsonl",p=>({dn:p.dn,note:p.note}),()=>
build("ka_all.geojsonl","cho_pt.geojsonl",p=>p.n?({n:p.n}):null)));
