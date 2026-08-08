// 北方領土标注的碎块归属修正。
//
// 旧做法：取南千岛 bbox 内的 OSM 陆地块，排除代表点落在北海道多边形里的。
// 漏洞：根室半岛外海那一圈**独立的小岛礁**（本来就不在北海道多边形内部）
// 全被当成北方領土收了进来，于是北海道海岸线上画出一串红虚线。
// 用户在真机上一眼看出来了。
//
// 新做法：最近邻归属。四岛主体（>10km²，共 6 块）当作"北方領土核心"，
// 北海道裁剪后的几何当作"北海道"，每个小块按代表点离谁近判给谁。
// 不手画任何范围框——这条是 README 里的红线。
"use strict";
const fs = require("fs");
const { area, bbox, repPoint } = require("/home/user/osm/geo.js");
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

// ── 北海道（裁剪后）的顶点 ────────────────────────────────
const prefOrder = fs.readFileSync(D + "/jp_pref.geojsonl", "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l).properties);
let hokVerts = [];
for (const l of fs.readFileSync(D + "/jp_pref_clip.geojsonl", "utf8").split("\n")) {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  const meta = prefOrder[f.properties.uid - 1];
  if (!meta || meta.code !== 1) continue;
  for (const poly of polysOnly(f.geometry) || []) for (const ring of poly) for (const p of ring) hokVerts.push(p);
}
if (!hokVerts.length) throw new Error("找不到裁剪后的北海道");

// ── 现有标注里的块 ────────────────────────────────────────
const feat = JSON.parse(fs.readFileSync(D + "/jp_disp.geojsonl", "utf8").split("\n")[0]);
const parts = feat.geometry.coordinates;
const info = parts.map(p => {
  const g = { type: "Polygon", coordinates: p };
  return { poly: p, a: Math.abs(area(g)) / 1e6, rp: repPoint(g) };
});
const CORE = 10;                       // km²，四岛主体
const cores = info.filter(p => p.a > CORE);
const rest  = info.filter(p => p.a <= CORE);
console.log("核心块 %d 个（%s km²），待判定 %d 个",
  cores.length, cores.reduce((s, p) => s + p.a, 0).toFixed(0), rest.length);

const coreVerts = [];
for (const c of cores) for (const ring of c.poly) for (const p of ring) coreVerts.push(p);

// 经纬度近似距离（km）。北纬 44 度附近，1° 经度 ≈ 80km，1° 纬度 ≈ 111km。
const KX = 80, KY = 111;
function nearest(pt, verts) {
  let best = Infinity;
  for (let i = 0; i < verts.length; i++) {
    const dx = (verts[i][0] - pt[0]) * KX, dy = (verts[i][1] - pt[1]) * KY;
    const d = dx * dx + dy * dy;
    if (d < best) best = d;
  }
  return Math.sqrt(best);
}

const keep = [...cores.map(c => c.poly)];
let dropped = 0, droppedArea = 0;
const dropSample = [];
for (const p of rest) {
  if (!p.rp) { dropped++; continue; }
  const dHok = nearest(p.rp, hokVerts);
  const dCore = nearest(p.rp, coreVerts);
  if (dCore <= dHok) keep.push(p.poly);
  else { dropped++; droppedArea += p.a; if (dropSample.length < 6) dropSample.push([p.rp, dHok, dCore]); }
}
const g = { type: "MultiPolygon", coordinates: keep };
const total = Math.abs(area(g)) / 1e6;
console.log("判给北海道而剔除：%d 块，合计 %s km²", dropped, droppedArea.toFixed(2));
dropSample.forEach(([rp, a, b]) => console.log("   例：%s,%s  离北海道 %skm 离四岛 %skm", rp[0].toFixed(3), rp[1].toFixed(3), a.toFixed(1), b.toFixed(1)));
console.log("保留 %d 块，面积 %s km²（四岛公开数字约 5,004）", keep.length, total.toFixed(0));
const bb = bbox(g);
console.log("保留部分范围：经度 %s~%s 纬度 %s~%s", bb[0].toFixed(3), bb[2].toFixed(3), bb[1].toFixed(3), bb[3].toFixed(3));

fs.writeFileSync(D + "/jp_disp_fixed.geojsonl",
  JSON.stringify({ type: "Feature", properties: feat.properties, geometry: g }) + "\n");
