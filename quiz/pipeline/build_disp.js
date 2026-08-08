// 争议/分歧范围图层。
//
// 规则（用户定的）：填色一律按**实际管理**；官方划法另外用虚线范围叠加并标注。
// 这条对国与国的争议、国内的省界分歧一视同仁。
//
// 范围多边形全部是算出来的或直接取自权威几何，没有一块是手画的：
//   唐古拉山  = 旧数据(官方口径)的青海 ∩ 新数据(OSM)的西藏
//   佤邦      = OSM 里南佤/北佤两个单元本身
//   藏南      = OSM 里印度阿鲁纳恰尔邦单元本身
//   其余 6 块 = 沿用既有争议区图层
"use strict";
const fs = require("fs");
const readline = require("readline");
const { topoToFeatures, area } = require("./geo.js");
const D = "/home/user/osm";

const out = [];
const push = (dn, note, deFacto, geometry) => {
  out.push({ type: "Feature", properties: { dn, note, de_facto: deFacto }, geometry });
};

// 1) 沿用既有的 6 块国际争议范围
const oldD = topoToFeatures(JSON.parse(fs.readFileSync("/home/user/-transit/quiz/ea_t2.topojson", "utf8")), "disp");
const NOTE = {
  "阿克赛钦":           ["印度主张",           "CHN"],
  "中印边界中段争议区":  ["中印双方主张不一",    "CHN"],
  "德姆乔克（典角）":    ["中印双方主张不一",    "CHN"],
  "德拉马纳-沙卡托":     ["中印双方主张不一",    "CHN"],
  "卡拉帕尼":           ["尼泊尔主张",         "IND"],
  "锡亚琴冰川":         ["巴基斯坦主张",       "IND"]
};
for (const f of oldD) {
  const dn = f.properties.dn;
  const [note, df] = NOTE[dn] || ["", ""];
  push(dn, note, df, f.geometry);
}

// 2) 唐古拉山：算出来的分歧范围
const tg = JSON.parse(fs.readFileSync(D + "/disp_tanggula.geojson", "utf8")).features[0];
push("唐古拉山地区", "官方划归青海省格尔木市；实际由西藏那曲方面管理", "CHN-西藏", tg.geometry);

// 3) 佤邦、藏南：直接取对应单元的几何
const wants = [
  ["MMR", ["南佤", "北佤"], "佤邦", "缅甸官方划属掸邦；实际由佤邦联合军自治", "MMR-佤邦"],
  ["IND", ["阿鲁纳恰尔邦"],  "藏南",  "中国主张为西藏一部分；实际由印度管理",   "IND"]
];
const found = {};
const rl = readline.createInterface({ input: fs.createReadStream(D + "/units_osm.geojsonl"), crlfDelay: Infinity });
rl.on("line", l => {
  if (!l.trim()) return;
  const f = JSON.parse(l);
  for (const [grp, names] of wants) {
    if (f.properties.grp !== grp) continue;
    for (const nm of names) {
      if (String(f.properties.n).includes(nm)) (found[grp + "|" + nm] = f);
    }
  }
});
rl.on("close", () => {
  for (const [grp, names, dn, note, df] of wants) {
    const parts = names.map(nm => found[grp + "|" + nm]).filter(Boolean);
    if (!parts.length) { console.log("!! 找不到:", dn, names.join("/")); continue; }
    const coords = [];
    for (const p of parts) {
      if (p.geometry.type === "Polygon") coords.push(p.geometry.coordinates);
      else coords.push(...p.geometry.coordinates);
    }
    push(dn, note, df, { type: "MultiPolygon", coordinates: coords });
  }
  fs.writeFileSync(D + "/disp_osm.geojsonl", out.map(f => JSON.stringify(f)).join("\n") + "\n");
  console.log("争议/分歧范围:", out.length, "块");
  out.forEach(f => console.log("  " + f.properties.dn.padEnd(12)
    + (Math.abs(area(f.geometry)) / 1e6).toFixed(0).padStart(8) + " km²  实控:"
    + String(f.properties.de_facto).padEnd(10) + f.properties.note));
});
