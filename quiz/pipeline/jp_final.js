// 把裁剪结果和属性合回去，产出可切瓦片的最终图层。
// uid = 写入 gpkg 时的 fid（1-based，与源文件行序一致）。
"use strict";
const fs = require("fs");
const readline = require("readline");
const { area } = require("./geo.js");
const D = "/home/user/osm";

const polysOnly = g => {
  if (!g) return null;
  if (/Polygon/.test(g.type)) return g;
  if (g.type !== "GeometryCollection") return null;
  const ps = [];
  g.geometries.forEach(s => { if (s.type === "Polygon") ps.push(s.coordinates); else if (s.type === "MultiPolygon") ps.push(...s.coordinates); });
  return ps.length ? { type: "MultiPolygon", coordinates: ps } : null;
};

function join(srcFile, clipFile, outFile, label, done) {
  const props = fs.readFileSync(D + "/" + srcFile, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l).properties);
  const out = fs.createWriteStream(D + "/" + outFile);
  let n = 0, miss = 0, tot = 0;
  const rl = readline.createInterface({ input: fs.createReadStream(D + "/" + clipFile), crlfDelay: Infinity });
  rl.on("line", l => {
    const s = l.replace(/^\x1e/, "").trim(); if (!s) return;
    let f; try { f = JSON.parse(s); } catch (e) { return; }
    const p = props[f.properties.uid - 1];
    if (!p) { miss++; return; }
    const g = polysOnly(f.geometry);
    if (!g) { miss++; return; }
    tot += Math.abs(area(g));
    out.write(JSON.stringify({ type: "Feature", properties: p, geometry: g }) + "\n");
    n++;
  });
  rl.on("close", () => {
    out.end();
    console.log(label + ": " + n + " 个（源 " + props.length + "），缺失 " + miss + "，合计 " + (tot / 1e6).toFixed(0) + " km²");
    if (n !== props.length) console.log("  !! 数量不符，必须查清楚");
    done && done();
  });
}

join("jp_pref.geojsonl", "jp_pref_clip.geojsonl", "jp_pref_final.geojsonl", "都道府県", () =>
  join("jp_muni.geojsonl", "jp_muni_clip.geojsonl", "jp_muni_final.geojsonl", "市町村"));
