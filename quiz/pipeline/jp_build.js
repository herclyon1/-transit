// 组装现代日本的地图数据：47 都道府県 + 市町村。
//
// 都道府県按 ISO3166-2 的 JP-01..JP-47 直接 join 旧表（JIS 代码），
// 不做几何匹配——今天在东亚数据上串名的那类问题在这里结构上不可能发生。
//
// 市町村用「代表点落在哪个都道府県内」归属，同时得到所属县代码。
"use strict";
const fs = require("fs");
const readline = require("readline");
const { contains, bbox, area, repPoint } = require("./geo.js");
const D = "/home/user/osm";

const { P, REGIONS } = JSON.parse(fs.readFileSync(D + "/jp_meta.json", "utf8"));

const pref = [], muni = [];
const rl = readline.createInterface({ input: fs.createReadStream(D + "/jp_raw.geojsonl"), crlfDelay: Infinity });
rl.on("line", l => {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) return;
  let f; try { f = JSON.parse(s); } catch (e) { return; }
  if (!f.geometry) return;
  const p = f.properties || {}, t = String(p.other_tags || "");
  const al = String(p.admin_level);
  if (al === "4") {
    const m = t.match(/"ISO3166-2"=>"JP-(\d{2})"/);
    if (!m) return;                               // 邻国的 AL4，丢弃
    pref.push({ code: Number(m[1]), name: p.name || "", g: f.geometry });
  } else if (al === "7") {
    muni.push({ name: p.name || "", zh: (t.match(/"name:zh"=>"([^"]*)"/) || [])[1] || "", g: f.geometry });
  }
});

rl.on("close", () => {
  console.log("都道府県", pref.length, " 市町村候选", muni.length);
  if (pref.length !== 47) throw new Error("都道府県不是 47 个，停下来查清楚");
  const seen = new Set(pref.map(x => x.code));
  for (let i = 1; i <= 47; i++) if (!seen.has(i)) throw new Error("缺 JP-" + i);

  pref.forEach(x => { x.bb = bbox(x.g); });

  // 市町村归属
  let inJP = 0, out = 0;
  for (const m of muni) {
    const rp = repPoint(m.g);
    if (!rp) { out++; continue; }
    const host = pref.find(p => rp[0] >= p.bb[0] && rp[0] <= p.bb[2] && rp[1] >= p.bb[1] && rp[1] <= p.bb[3] && contains(p.g, rp));
    if (!host) { out++; continue; }
    m.pref = host.code; inJP++;
  }
  console.log("市町村：日本境内", inJP, " 境外(邻国)", out);

  // 写出
  const wp = fs.createWriteStream(D + "/jp_pref.geojsonl");
  for (const x of pref) {
    const meta = P[x.code];
    wp.write(JSON.stringify({ type: "Feature", geometry: x.g, properties: {
      code: x.code, n: meta[0], cap: meta[1], reg: meta[2], regn: REGIONS[meta[2]], osm: x.name } }) + "\n");
  }
  wp.end();

  const wm = fs.createWriteStream(D + "/jp_muni.geojsonl");
  let mw = 0;
  for (const m of muni) {
    if (!m.pref) continue;
    wm.write(JSON.stringify({ type: "Feature", geometry: m.g, properties: {
      n: m.name, zh: m.zh, pref: m.pref, prefn: P[m.pref][0] } }) + "\n");
    mw++;
  }
  wm.end();

  // 面积校验：日本国土 377,975 km²
  const tot = pref.reduce((a, x) => a + Math.abs(area(x.g)), 0) / 1e6;
  console.log("\n都道府県合计面积", tot.toFixed(0), "km²（实际 377,975，裁剪前含领海会偏大）");
  const probe = [1, 13, 27, 47];
  const real = { 1: 83424, 13: 2194, 27: 1905, 47: 2282 };
  for (const c of probe) {
    const x = pref.find(y => y.code === c);
    console.log("  " + P[c][0].padEnd(6) + (Math.abs(area(x.g)) / 1e6).toFixed(0).padStart(8) + " km²  实际 " + real[c]);
  }
  console.log("\n写出 jp_pref.geojsonl(" + pref.length + ") jp_muni.geojsonl(" + mw + ")");
});
