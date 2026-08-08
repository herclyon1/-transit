// 逐层级验收瓦片里的边界精度。
//
// 为什么必须做：tippecanoe 按缩放级别做的简化，和当年 mapshaper 的 `interval`
// 是同一类陷阱——`interval` 是面积阈值不是段长阈值，误解那一点把中蒙国界从
// 91m 削到了 1469m，而当时没人量过，所以上线才发现。
//
// 用法: node verify_tiles.js <tippecanoe-decode 出来的 geojson> <层级>
"use strict";
const fs = require("fs");
const R = 6371008.8, rad = Math.PI / 180;

const segs = [];
function walk(c) {
  if (typeof c[0][0] === "number") {
    for (let i = 1; i < c.length; i++) {
      const a = c[i - 1], b = c[i];
      const dy = (b[1] - a[1]) * rad, dx = (b[0] - a[0]) * rad * Math.cos((a[1] + b[1]) / 2 * rad);
      const d = Math.hypot(dx, dy) * R;
      if (d > 0) segs.push(d);
    }
  } else c.forEach(walk);
}

const txt = fs.readFileSync(process.argv[2], "utf8");
let nf = 0;
for (const line of txt.split("\n")) {
  const s = line.trim();
  if (!s || s[0] !== "{") continue;
  let f; try { f = JSON.parse(s.replace(/,$/, "")); } catch (e) { continue; }
  if (!f.geometry) continue;
  nf++;
  walk(f.geometry.coordinates);
}
segs.sort((a, b) => a - b);
const q = p => segs[Math.floor(segs.length * p)] || 0;
console.log("z" + (process.argv[3] || "?"), " 要素", nf, " 线段", segs.length,
  " 中位", q(.5).toFixed(0) + "m", " p90", q(.9).toFixed(0) + "m", " 最长", (segs[segs.length - 1] || 0).toFixed(0) + "m");
