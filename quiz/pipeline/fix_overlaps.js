// 修三个由「自己合成几何」引入的问题。用户的判断是对的：
// 「标注的特殊区域…那个是你自己画的最容易出问题」。
//
// 1) 唐古拉山标注被切成 186 块。用两份数据求交，除了真正有分歧的那一大块
//    （59,017 km²，占 99.7%），沿整条青藏省界还产生了 185 片 10 km² 以下的锯齿噪声。
//    两份数据的边界来回交错，必然如此。只保留 ≥100 km² 的块。
//
// 2) 马绍尔群岛画了两套：OSM 的 2 条礁链 + 旧数据的 22 个市镇，22 个套在 2 个里面。
//    合并时的疏忽，应当二选一。保留 22 个（旧数据，粒度和答题一致）。
//
// 3) 缅甸掸邦和佤邦重叠——佤邦既单列又还在掸邦里面。掸邦必须扣掉佤邦。
//    （布尔差集在 fix_shan.sh 里用 ST_Difference 做，这里只标出来。）
"use strict";
const fs = require("fs");
const { area } = require("./geo.js");
const D = "/home/user/osm";

// ---- 1) 清掉唐古拉山的锯齿碎片 ----
const disp = [];
let dropped = 0;
for (const l of fs.readFileSync(D + "/disp_osm.geojsonl", "utf8").split("\n")) {
  if (!l.trim()) continue;
  const f = JSON.parse(l);
  if (f.geometry.type === "MultiPolygon" && f.geometry.coordinates.length > 1) {
    const keep = f.geometry.coordinates.filter(p => {
      const a = Math.abs(area({ type: "Polygon", coordinates: p })) / 1e6;
      if (a < 100) { dropped++; return false; }
      return true;
    });
    if (keep.length) f.geometry = { type: "MultiPolygon", coordinates: keep };
  }
  disp.push(f);
}
fs.writeFileSync(D + "/disp_fixed.geojsonl", disp.map(f => JSON.stringify(f)).join("\n") + "\n");
console.log("标注层：剔除 <100km² 的碎片", dropped, "块");
disp.forEach(f => {
  const n = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates.length : 1;
  console.log("  " + f.properties.dn.padEnd(12) + " 块数 " + n + "  " + (Math.abs(area(f.geometry)) / 1e6).toFixed(0) + " km²");
});

// ---- 2) 马绍尔去掉 OSM 的两条礁链 ----
const CHAIN = new Set(["拉利克礁链", "拉塔克礁链"]);
const out = fs.createWriteStream(D + "/units_fixed.geojsonl");
let kept = 0, rm = 0, shan = null, wa = [];
for (const l of fs.readFileSync(D + "/units_osm.geojsonl", "utf8").split("\n")) {
  if (!l.trim()) continue;
  const f = JSON.parse(l);
  if (f.properties.grp === "MHL" && CHAIN.has(f.properties.n)) { rm++; continue; }
  if (f.properties.grp === "MMR" && f.properties.n === "掸邦") { shan = f; continue; }
  if (f.properties.grp === "MMR" && (f.properties.n === "南佤" || f.properties.n === "北佤")) wa.push(f);
  out.write(JSON.stringify(f) + "\n"); kept++;
}
out.end();
console.log("\n马绍尔：剔除 OSM 礁链", rm, "个（保留旧数据的 22 个市镇）");
fs.writeFileSync(D + "/shan.geojson", JSON.stringify({ type: "FeatureCollection", features: [shan] }));
fs.writeFileSync(D + "/wa.geojson", JSON.stringify({ type: "FeatureCollection", features: wa }));
console.log("掸邦与佤邦已导出，待做布尔差集。单元数（暂缺掸邦）:", kept);
