// 水体和河流按尺度筛选。
//
// 原始抽取是 221 万个水体 + 55 万段河流（4GB）——把每口池塘、每段小溪都算进来了。
// 东亚全图 z0-12 用不到这个粒度，切出来的瓦片也会爆掉 GitHub 的 100MB 单文件上限。
//
// 阈值不是拍脑袋定的，是量完分布定的：
//   ≥1000 km²: 32 个   100-1000: 502   10-100: 4234   1-10: 25226
//   0.1-1: 113231      <0.1: 2071477
// 取 ≥1 km²（约 3 万个）能覆盖到所有认得出名字的湖，同时把池塘全部挡掉。
// 有名字且 ≥0.1 km² 的额外放行，避免漏掉细长的知名水体。
"use strict";
const fs = require("fs");
const readline = require("readline");
const { area } = require("./geo.js");
const D = "/home/user/osm";

const R = 6371008.8, rad = Math.PI / 180;
function lineLen(g) {
  let L = 0;
  const walk = c => {
    if (typeof c[0][0] === "number") {
      for (let i = 1; i < c.length; i++) {
        const a = c[i - 1], b = c[i];
        const dy = (b[1] - a[1]) * rad, dx = (b[0] - a[0]) * rad * Math.cos((a[1] + b[1]) / 2 * rad);
        L += Math.hypot(dx, dy) * R;
      }
    } else c.forEach(walk);
  };
  walk(g.coordinates);
  return L;
}

function run(inFile, outFile, keep, done) {
  const out = fs.createWriteStream(D + "/" + outFile);
  let n = 0, kept = 0;
  const rl = readline.createInterface({ input: fs.createReadStream(D + "/" + inFile), crlfDelay: Infinity });
  rl.on("line", l => {
    const s = l.replace(/^\x1e/, "").trim(); if (!s) return;
    let f; try { f = JSON.parse(s); } catch (e) { return; }
    if (!f.geometry) return;
    n++;
    const p = keep(f);
    if (!p) return;
    out.write(JSON.stringify({ type: "Feature", properties: p, geometry: f.geometry }) + "\n");
    kept++;
  });
  rl.on("close", () => { out.end(); console.log(inFile, "读入", n, "保留", kept); done && done(); });
}

run("water_raw.geojsonl", "water_osm.geojsonl", f => {
  const a = Math.abs(area(f.geometry)) / 1e6;
  const nm = (f.properties && (f.properties.name || "")) || "";
  if (a < 1 && !(nm && a >= 0.1)) return null;
  const t = String((f.properties && f.properties.other_tags) || "");
  return { n: (t.match(/"name:zh"=>"([^"]*)"/) || [])[1] || nm, a: Math.round(a) };
}, () => {
  // 河流：只留干流。按单段长度筛会把长河切碎的每一段都算短，
  // 所以同时放行「有名字」的段——OSM 里干流的每一段都带 name。
  run("rivers_raw.geojsonl", "rivers_osm.geojsonl", f => {
    const nm = (f.properties && (f.properties.name || "")) || "";
    const L = lineLen(f.geometry);
    if (!nm && L < 20000) return null;
    if (nm && L < 2000) return null;
    const t = String((f.properties && f.properties.other_tags) || "");
    return { n: (t.match(/"name:zh"=>"([^"]*)"/) || [])[1] || nm };
  });
});
