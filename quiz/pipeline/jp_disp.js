// 日本地图的争议/主张范围标注。
//
// 规则同东亚：填色按实际管理，官方主张另出虚线范围 + 标注。
//
// 北方領土（择捉・国后・色丹・歯舞）由俄罗斯实际管理，所以不在北海道的填色里，
// 这正是裁剪后北海道比日本官方数字少 5,145 km² 的原因（四岛合计约 5,004 km²）。
// 我们的提取范围里没有俄方的行政单元，但标注要的就是**岛屿轮廓本身**，
// 直接从 OSM 陆地多边形取即可，不需要为此下载整个俄罗斯。
"use strict";
const fs = require("fs");
const readline = require("readline");
const { contains, bbox, area, repPoint } = require("./geo.js");
const D = "/home/user/osm";

// 北海道（已裁剪）用来排除本岛及其属岛
const prefOrder = fs.readFileSync(D + "/jp_pref.geojsonl", "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l).properties);
const polysOnly = g => {
  if (!g) return null;
  if (/Polygon/.test(g.type)) return g;
  if (g.type !== "GeometryCollection") return null;
  const ps = [];
  g.geometries.forEach(s => { if (s.type === "Polygon") ps.push(s.coordinates); else if (s.type === "MultiPolygon") ps.push(...s.coordinates); });
  return ps.length ? { type: "MultiPolygon", coordinates: ps } : null;
};

let hokkaido = null;
const rl = readline.createInterface({ input: fs.createReadStream(D + "/jp_pref_clip.geojsonl"), crlfDelay: Infinity });
rl.on("line", l => {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) return;
  let f; try { f = JSON.parse(s); } catch (e) { return; }
  const meta = prefOrder[f.properties.uid - 1];
  if (!meta || meta.code !== 1) return;
  hokkaido = polysOnly(f.geometry);
});

rl.on("close", () => {
  if (!hokkaido) throw new Error("找不到裁剪后的北海道");
  const hbb = bbox(hokkaido);
  console.log("北海道面积", (Math.abs(area(hokkaido)) / 1e6).toFixed(0), "km²");

  // 千岛南部范围内的陆地块，排除属于北海道的
  const parts = [];
  const lines = fs.readFileSync(D + "/kuril_land.geojsonl", "utf8").split("\n");
  for (const l of lines) {
    const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
    let f; try { f = JSON.parse(s); } catch (e) { continue; }
    if (!f.geometry) continue;
    const rp = repPoint(f.geometry);
    if (!rp) continue;
    const inHok = rp[0] >= hbb[0] && rp[0] <= hbb[2] && rp[1] >= hbb[1] && rp[1] <= hbb[3] && contains(hokkaido, rp);
    if (inHok) continue;
    if (f.geometry.type === "Polygon") parts.push(f.geometry.coordinates);
    else if (f.geometry.type === "MultiPolygon") parts.push(...f.geometry.coordinates);
  }
  const g = { type: "MultiPolygon", coordinates: parts };
  const a = Math.abs(area(g)) / 1e6;
  console.log("北方領土 块数", parts.length, " 面积", a.toFixed(0), "km²（四岛实际约 5,004）");

  const out = [{ type: "Feature", properties: {
    dn: "北方領土", note: "日本主张为北海道一部分；实际由俄罗斯管理", de_facto: "RUS" }, geometry: g }];
  fs.writeFileSync(D + "/jp_disp.geojsonl", out.map(f => JSON.stringify(f)).join("\n") + "\n");
  console.log("写出 jp_disp.geojsonl");
});
