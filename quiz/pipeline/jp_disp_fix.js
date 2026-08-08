// 北方領土标注的归属修正（第二版）。
//
// 第一版用「离北海道近还是离四岛近」的最近邻判定，把**貝殻島**判错了——
// 它离納沙布岬只有 3.7km，比离水晶島还近，于是被剔除，结果两边都不画，岛凭空消失。
// 用户一句「你把北海道那边的岛给删了？」正好戳中。
//
// 真正的判据根本不需要距离：**裁剪后的北海道多边形本身就是分界线**。
// OSM 里北方四岛不属于日本的行政区划，所以凡是落在北海道多边形里的都是北海道的属岛，
// 落在外面的才是北方領土。
//
// 原来那版之所以会把根室沿岸的岛礁收进来，是因为它按**要素**判定：
// kuril_land 里一个要素可能是 MultiPolygon，只要它的代表点落在北海道外，
// 它的**所有部件**就都被收了进去。改成逐**部件**判定即可。
"use strict";
const fs = require("fs");
const { area, bbox, repPoint, contains } = require("/home/user/osm/geo.js");
const D = "/home/user/osm";

const polysOnly = g => {
  if (!g) return null;
  if (g.type === "Polygon") return [g.coordinates];
  if (g.type === "MultiPolygon") return g.coordinates;
  if (g.type !== "GeometryCollection") return null;
  const ps = [];
  g.geometries.forEach(s => { if (s.type === "Polygon") ps.push(s.coordinates); else if (s.type === "MultiPolygon") ps.push(...s.coordinates); });
  return ps;
};

const prefOrder = fs.readFileSync(D + "/jp_pref.geojsonl", "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l).properties);
let hok = null;
for (const l of fs.readFileSync(D + "/jp_pref_clip.geojsonl", "utf8").split("\n")) {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  const meta = prefOrder[f.properties.uid - 1];
  if (!meta || meta.code !== 1) continue;
  const ps = polysOnly(f.geometry);
  hok = { type: "MultiPolygon", coordinates: ps };
}
if (!hok) throw new Error("找不到裁剪后的北海道");
const hbb = bbox(hok);

const feat = JSON.parse(fs.readFileSync(D + "/jp_disp.geojsonl", "utf8").split("\n")[0]);
const parts = feat.geometry.coordinates;
const keep = [], drop = [];
for (const p of parts) {
  const rp = repPoint({ type: "Polygon", coordinates: p });
  if (!rp) continue;
  const inHok = rp[0] >= hbb[0] && rp[0] <= hbb[2] && rp[1] >= hbb[1] && rp[1] <= hbb[3] && contains(hok, rp);
  (inHok ? drop : keep).push(p);
}
const g = { type: "MultiPolygon", coordinates: keep };
const A = c => Math.abs(area({ type: "MultiPolygon", coordinates: c })) / 1e6;
console.log("源部件 %d：判给北海道 %d 块（%s km²），保留为北方領土 %d 块（%s km²，公开约 5,004）",
  parts.length, drop.length, A(drop).toFixed(2), keep.length, A(keep).toFixed(0));
const bb = bbox(g);
console.log("保留部分范围：经度 %s~%s 纬度 %s~%s", bb[0].toFixed(3), bb[2].toFixed(3), bb[1].toFixed(3), bb[3].toFixed(3));
// 貝殻島 必须还在
const kai = keep.some(p => { const r = repPoint({ type: "Polygon", coordinates: p }); return r && Math.abs(r[0] - 145.858) < .02 && Math.abs(r[1] - 43.3965) < .02; });
console.log("貝殻島（145.858,43.397）在保留集合里：" + (kai ? "是" : "否 —— 有问题"));

fs.writeFileSync(D + "/jp_disp_fixed.geojsonl",
  JSON.stringify({ type: "Feature", properties: feat.properties, geometry: g }) + "\n");
