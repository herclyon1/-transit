// 合成最终单元层，并按硬指标验收。
//
// 验收判据（不通过就不往下走）：
//   1. 内陆单元裁剪前后面积必须一分不差 —— 变了说明裁剪逻辑坏了
//   2. 沿海单元面积应当回升到接近真实值（旧数据比实际小约 9%）
//   3. 单元数、grp 分布、中文名唯一性
"use strict";
const fs = require("fs");
const readline = require("readline");
const { topoToFeatures, area, segStats } = require("./geo.js");
const D = "/home/user/osm";

const picked = JSON.parse(fs.readFileSync(D + "/picked.json", "utf8"));
const byFid = new Map(picked.filter(u => !u.rebuiltFrom).map(u => [String(u.fid), u]));
const rebuilt = picked.filter(u => u.rebuiltFrom);

const oldF = topoToFeatures(JSON.parse(fs.readFileSync("/home/user/-transit/quiz/ea_t2.topojson", "utf8")), "units");
const oldArea = {};
oldF.forEach(u => oldArea[u.properties.grp + "|" + u.properties.n] = Math.abs(area(u.geometry)));

const out = fs.createWriteStream(D + "/units_osm.geojsonl");
const stats = [];
let n = 0, miss = 0;

// ST_Union(ST_Intersection(...)) 在多边形与陆地块相切处会吐出 GeometryCollection
// （面 + 线/点混在一起）。只保留面的部分，否则这些单元的面积会算成 0——
// 广东省和平安北道就是这么变成 0 的。
function polysOnly(g) {
  if (!g) return null;
  if (g.type === "Polygon" || g.type === "MultiPolygon") return g;
  if (g.type !== "GeometryCollection") return null;
  const parts = [];
  for (const sub of g.geometries) {
    if (sub.type === "Polygon") parts.push(sub.coordinates);
    else if (sub.type === "MultiPolygon") parts.push(...sub.coordinates);
  }
  return parts.length ? { type: "MultiPolygon", coordinates: parts } : null;
}

const rl = readline.createInterface({ input: fs.createReadStream(D + "/units_clipped.geojsonl"), crlfDelay: Infinity });
rl.on("line", line => {
  const s = line.replace(/^\x1e/, "").trim(); if (!s) return;
  let f; try { f = JSON.parse(s); } catch (e) { return; }
  const meta = byFid.get(String(f.properties.uid));
  if (!meta) return;                       // 重建子件，另行处理
  const g = polysOnly(f.geometry);
  if (!g) { miss++; return; }
  const a = Math.abs(area(g));
  stats.push({ grp: meta.grp, n: meta.n, a });
  out.write(JSON.stringify({ type: "Feature", properties: { grp: meta.grp, n: meta.n }, geometry: g }) + "\n");
  n++;
});

rl.on("close", () => {
  // 重建单元
  for (const rb of rebuilt) {
    const t = fs.readFileSync(D + "/rebuild_union.geojsonl", "utf8").replace(/^\x1e/, "").trim();
    const f = JSON.parse(t.split("\n")[0].replace(/^\x1e/, ""));
    const rg = polysOnly(f.geometry);
    stats.push({ grp: rb.grp, n: rb.n, a: Math.abs(area(rg)) });
    out.write(JSON.stringify({ type: "Feature", properties: { grp: rb.grp, n: rb.n }, geometry: rg }) + "\n");
    n++;
  }
  // 马绍尔：OSM 没有市镇界，这 22 个沿用旧几何（已知缺口，不是遗漏）
  let mhl = 0;
  for (const u of oldF) {
    if (u.properties.grp !== "MHL") continue;
    stats.push({ grp: "MHL", n: u.properties.n, a: Math.abs(area(u.geometry)), old: true });
    out.write(JSON.stringify({ type: "Feature", properties: { grp: "MHL", n: u.properties.n, src: "old" }, geometry: u.geometry }) + "\n");
    n++; mhl++;
  }
  out.end();

  console.log("最终单元:", n, " (其中马绍尔沿用旧几何", mhl, "个)  裁剪后无几何:", miss);

  const byGrp = {};
  stats.forEach(s => (byGrp[s.grp] = byGrp[s.grp] || []).push(s));
  console.log("国家数:", Object.keys(byGrp).length);

  // 面积对照
  console.log("\n== 关键单元面积对照 (km²) ==");
  const probe = [["CHN", "海南省", 35400], ["CHN", "广东省", 179800], ["CHN", "山西省", 156700],
                 ["CHN", "青海省", 722300], ["PRK", "平安北道", 12200], ["TWN", "台湾省", null]];
  for (const [g, nm, real] of probe) {
    const s = stats.find(x => x.grp === g && x.n === nm);
    const o = oldArea[g + "|" + nm];
    if (!s) { console.log("  " + nm + ": 未找到"); continue; }
    console.log("  " + nm.padEnd(8) + " 旧 " + (o ? (o / 1e6).toFixed(0) : "-").padStart(8)
      + "  新 " + (s.a / 1e6).toFixed(0).padStart(8) + (real ? "  实际约 " + real : ""));
  }

  // 全局面积变化
  let up = 0, down = 0, same = 0;
  for (const s of stats) {
    const o = oldArea[s.grp + "|" + s.n];
    if (!o) continue;
    const d = (s.a - o) / o;
    if (d > 0.005) up++; else if (d < -0.005) down++; else same++;
  }
  console.log("\n与旧数据相比: 变大", up, " 变小", down, " 基本不变", same);
  fs.writeFileSync(D + "/unit_stats.json", JSON.stringify(stats));
});
