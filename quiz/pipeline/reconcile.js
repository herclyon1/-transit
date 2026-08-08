// 把 OSM 抽出来的行政区多边形，跟旧的 612 个单元对账。
//
// 设计：几何取 OSM（权威），中文名和 grp 从旧数据按代表点归属继承。
// 每个国家该取哪一级 admin_level 不是拍脑袋定的，而是实测出来的——
// 逐级试，选跟旧单元一一对应得最好的那一级。
"use strict";
const fs = require("fs");
const { topoToFeatures, area, repPoint, contains, bbox } = require("./geo.js");

const OLD = "/home/user/-transit/quiz/ea_t2.topojson";
const NEW = process.argv[2] || "/home/user/osm/adm.geojsonl";

// ---- 旧单元索引 ----
const oldF = topoToFeatures(JSON.parse(fs.readFileSync(OLD, "utf8")), "units");
oldF.forEach(u => { u.bb = bbox(u.geometry); });
console.log("旧单元:", oldF.length, " 国家:", new Set(oldF.map(u => u.properties.grp)).size);

function findOld(pt) {
  for (const u of oldF) {
    if (pt[0] < u.bb[0] || pt[0] > u.bb[2] || pt[1] < u.bb[1] || pt[1] > u.bb[3]) continue;
    if (contains(u.geometry, pt)) return u;
  }
  return null;
}

// ---- 读 OSM 候选 ----
const cands = [];
for (const line of fs.readFileSync(NEW, "utf8").split("\n")) {
  const s = line.replace(/^\x1e/, "").trim();
  if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  if (!f.geometry || !/Polygon/.test(f.geometry.type)) continue;
  const p = f.properties || {};
  const al = String(p.admin_level || "");
  if (!/^[2-6]$/.test(al)) continue;
  const a = area(f.geometry);
  if (a < 1e6) continue;                 // 小于 1 km² 的忽略（多为误标的建筑）
  const rp = repPoint(f.geometry);
  if (!rp) continue;
  cands.push({ f, al, a, rp, name: p.name || "", iso: p["ISO3166-2"] || "" });
}
console.log("OSM 候选多边形 (AL2-6, >1km²):", cands.length);

// ---- 每个候选归属到旧单元 ----
let unmatched = 0;
for (const c of cands) {
  const o = findOld(c.rp);
  if (o) { c.grp = o.properties.grp; c.oldName = o.properties.n; }
  else unmatched++;
}
console.log("代表点落在旧覆盖范围之外的候选:", unmatched, "(区域外的邻国，正常)");

// ---- 逐国选级 ----
const oldByGrp = {};
oldF.forEach(u => (oldByGrp[u.properties.grp] = oldByGrp[u.properties.grp] || []).push(u.properties.n));

const chosen = {}, report = [];
for (const grp of Object.keys(oldByGrp).sort()) {
  const want = oldByGrp[grp].length;
  const byLv = {};
  cands.filter(c => c.grp === grp).forEach(c => (byLv[c.al] = byLv[c.al] || []).push(c));
  let best = null;
  for (const al of Object.keys(byLv)) {
    const list = byLv[al];
    const hitNames = new Set(list.map(c => c.oldName));
    // 打分：覆盖到的旧单元数优先，其次候选数与期望数的接近程度
    const score = hitNames.size * 1000 - Math.abs(list.length - want);
    if (!best || score > best.score) best = { al, list, cover: hitNames.size, score };
  }
  if (!best) { report.push([grp, want, "-", 0, 0, "无候选"]); continue; }
  chosen[grp] = best.al;
  const flag = best.cover === want && best.list.length === want ? "OK"
             : best.cover === want ? "数量不符"
             : "缺 " + (want - best.cover) + " 个";
  report.push([grp, want, "AL" + best.al, best.list.length, best.cover, flag]);
}

console.log("\ngrp   期望  选级   候选数  覆盖旧单元  判定");
let bad = 0;
for (const r of report) {
  if (r[5] !== "OK") bad++;
  console.log(String(r[0]).padEnd(6) + String(r[1]).padStart(4) + "  " + String(r[2]).padEnd(6)
    + String(r[3]).padStart(6) + String(r[4]).padStart(11) + "   " + r[5]);
}
console.log("\n不达标国家:", bad, "/", report.length);

fs.writeFileSync("/home/user/osm/level_map.json", JSON.stringify(chosen, null, 1));
console.log("已写出 level_map.json");
