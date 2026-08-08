// 把水体和河流裁到地图覆盖范围内。
//
// 用户上一轮已经报过一次这个 bug：「地图国家范围外的水体河流不要加进去，
// 我第一眼还以为又渲染错误了」。这次从大洋洲提取包抽水系时又犯了，
// 澳大利亚整片河网画在了海面上。
//
// 判据：要素的代表点必须落在覆盖国家的国界内。日本要保留——
// 正式版里日本由 admin1 单独绘制，是地图的一部分。
"use strict";
const fs = require("fs");
const readline = require("readline");
const { contains, bbox } = require("./geo.js");
const D = "/home/user/osm";

const COVER = new Set(["CHN","TWN","PRK","KOR","MNG","VNM","THA","PHL","IDN","IND","MMR","MYS",
  "SGP","BRN","KHM","LAO","BGD","NPL","BTN","LKA","MDV","TLS","PNG","MHL","PLW","FSM","MNP","JPN"]);

const countries = [];
for (const l of fs.readFileSync(D + "/countries.geojsonl", "utf8").split("\n")) {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  if (!f.geometry) continue;
  const iso = (String(f.properties.other_tags || "").match(/"ISO3166-1:alpha3"=>"([A-Z]{3})"/) || [])[1];
  if (iso && COVER.has(iso)) countries.push({ iso, g: f.geometry, bb: bbox(f.geometry) });
}
// 菲律宾和北马里亚纳在 OSM 里没有自己的 AL2 国界多边形，
// 只按国界过滤会把它们的水系整片误删。用它们的行政单元几何补上覆盖范围。
{
  const missing = new Set([...COVER].filter(c => !countries.some(x => x.iso === c)));
  if (missing.size) {
    const txt = fs.readFileSync(D + "/units_osm.geojsonl", "utf8").split("\n");
    let added = 0;
    for (const l of txt) {
      if (!l.trim()) continue;
      let f; try { f = JSON.parse(l); } catch (e) { continue; }
      if (!missing.has(f.properties.grp)) continue;
      countries.push({ iso: f.properties.grp, g: f.geometry, bb: bbox(f.geometry) });
      added++;
    }
    console.log("用行政单元补覆盖范围:", [...missing].join(","), "共", added, "个单元");
  }
}
console.log("覆盖多边形:", countries.length);

function inside(pt) {
  for (const c of countries) {
    if (pt[0] < c.bb[0] || pt[0] > c.bb[2] || pt[1] < c.bb[1] || pt[1] > c.bb[3]) continue;
    if (contains(c.g, pt)) return true;
  }
  return false;
}

function midPoint(g) {
  const pts = [];
  const w = c => { if (typeof c[0] === "number") pts.push(c); else c.forEach(w); };
  w(g.coordinates);
  return pts.length ? pts[Math.floor(pts.length / 2)] : null;
}

function filter(inF, outF, done) {
  const out = fs.createWriteStream(D + "/" + outF);
  let n = 0, kept = 0;
  const rl = readline.createInterface({ input: fs.createReadStream(D + "/" + inF), crlfDelay: Infinity });
  rl.on("line", l => {
    const s = l.trim(); if (!s) return;
    let f; try { f = JSON.parse(s); } catch (e) { return; }
    if (!f.geometry) return;
    n++;
    const p = midPoint(f.geometry);
    if (!p || !inside(p)) return;
    out.write(JSON.stringify(f) + "\n"); kept++;
  });
  rl.on("close", () => {
    out.end();
    console.log(inF, "读入", n, "保留", kept, "剔除", n - kept);
    done && done();
  });
}

filter("water_osm.geojsonl", "water_cov.geojsonl", () =>
  filter("rivers_osm.geojsonl", "rivers_cov.geojsonl"));
