// 选出最终行政单元集合，决定每个单元的 grp 与中文名。
//
// 两处刻意的设计，都是踩过坑之后定的：
//
// 1) 国家归属：先用代表点落在哪个 OSM 国界多边形内；国界没组装成功的国家
//    （菲律宾、北马里亚纳等）退回 ISO3166-2 标签前缀。只用其中一种都会漏。
//
// 2) 中文名继承：方向是「旧单元的代表点落在哪个 OSM 多边形里」，不是反过来。
//    旧数据比实际小约 9%，OSM 沿海单元的代表点常落在旧多边形之外；反方向则
//    因为 OSM 多边形更大而稳定命中，且天然保证一个旧单元只认领一个 OSM 单元。
"use strict";
const fs = require("fs");
const { contains, bbox, topoToFeatures, area } = require("./geo.js");
const D = "/home/user/osm";

const ISO2TO3 = { CN:"CHN",TW:"TWN",KP:"PRK",KR:"KOR",MN:"MNG",VN:"VNM",TH:"THA",PH:"PHL",
  ID:"IDN",IN:"IND",MM:"MMR",MY:"MYS",SG:"SGP",BN:"BRN",KH:"KHM",LA:"LAO",BD:"BGD",
  NP:"NPL",BT:"BTN",LK:"LKA",MV:"MDV",TL:"TLS",PG:"PNG",MH:"MHL",PW:"PLW",FM:"FSM",MP:"MNP" };

// 实测得出：绝大多数国家的一级行政区在 AL4。例外都在这里，并注明原因。
const LEVEL = {
  LKA: ["5"],        // AL4 是 9 个省，旧数据用的是 25 个县 = AL5
  SGP: ["5"],        // 5 个社区发展理事会区在 AL5，且都没打 ISO3166-2
  MNP: ["6"],        // 美属，4 个自治市在 AL6
  CHN: ["4", "3"],   // 31 个省级在 AL4，港澳在 AL3
  _d:  ["4"]
};

// ---- 国界多边形 ----
const countries = [];
for (const l of fs.readFileSync(D + "/countries.geojsonl", "utf8").split("\n")) {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  if (!f.geometry) continue;
  const iso = (String(f.properties.other_tags || "").match(/"ISO3166-1:alpha3"=>"([A-Z]{3})"/) || [])[1];
  if (iso) countries.push({ iso, g: f.geometry, bb: bbox(f.geometry) });
}

function whichCountry(pt) {
  for (const c of countries) {
    if (pt[0] < c.bb[0] || pt[0] > c.bb[2] || pt[1] < c.bb[1] || pt[1] > c.bb[3]) continue;
    if (contains(c.g, pt)) return c.iso;
  }
  return null;
}

// ---- 旧单元 ----
const oldF = topoToFeatures(JSON.parse(fs.readFileSync("/home/user/-transit/quiz/ea_t2.topojson", "utf8")), "units");
const WANT = {};
oldF.forEach(u => WANT[u.properties.grp] = (WANT[u.properties.grp] || 0) + 1);

// 旧单元代表点：用最大环的重心，落不进就沿环找
const { repPoint } = require("./geo.js");
oldF.forEach(u => { u.rp = repPoint(u.geometry); });

// ---- OSM 候选（简化几何，仅用于匹配） ----
const cands = [];
for (const l of fs.readFileSync(D + "/adm_simp.geojsonl", "utf8").split("\n")) {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  if (!f.geometry || !/Polygon/.test(f.geometry.type)) continue;
  const p = f.properties || {};
  const t = String(p.other_tags || "");
  const iso2 = (t.match(/"ISO3166-2"=>"([A-Z]{2})-/) || [])[1];
  cands.push({
    fid: p.uid, al: String(p.admin_level), name: p.name || "",
    zh: (t.match(/"name:zh"=>"([^"]*)"/) || [])[1] || "",
    isoTag: iso2 ? ISO2TO3[iso2] : null,
    g: f.geometry, bb: bbox(f.geometry), a: Math.abs(area(f.geometry))
  });
}
console.log("OSM 候选:", cands.length, " 国界多边形:", countries.length, " 旧单元:", oldF.length);

// 补国界：有些属地在 OSM 里没有自己的 AL2 国界，只挂在宗主国下面。
// 北马里亚纳的 4 个自治市就因此全部归属失败——它们的代表点落在
// "United States of America (CNMI)" 里，而美国不在覆盖范围内，于是被整体丢掉。
for (const c of cands) {
  if (c.al === "4" && c.name === "Northern Mariana Islands") countries.push({ iso: "MNP", g: c.g, bb: c.bb });
}

// 断言：id 必须存在且唯一。
// 上一版这里是坏的——ogr2ogr 把 `fid AS src_fid` 这个列丢掉了，导致每个候选的 id
// 都是 undefined，于是全部单元共用同一条名字记录，而报表还显示「0 个未继承中文名」。
// 检查本身是坏的，比没有检查更危险，所以这条断言必须留着。
{
  const ids = cands.map(c => c.fid);
  if (ids.some(x => x === undefined || x === null)) throw new Error("候选缺少 uid —— 导出时列被丢了");
  if (new Set(ids).size !== ids.length) throw new Error("候选 uid 不唯一");
}

// ---- 定国 ----
// 用 ST_PointOnSurface 算出的真代表点，不能用 bbox 中心：
// 弯曲或群岛型行政区的 bbox 中心会落到海里甚至邻国，台湾/泰国/越南就是这么丢的。
const RP = {};
for (const l of fs.readFileSync(D + "/adm_pts.geojsonl", "utf8").split("\n")) {
  const s = l.replace(/^\x1e/, "").trim(); if (!s) continue;
  let f; try { f = JSON.parse(s); } catch (e) { continue; }
  if (f.geometry && f.geometry.type === "Point") RP[f.properties.uid] = f.geometry.coordinates;
}
for (const c of cands) {
  c.rp = RP[c.fid] || [(c.bb[0] + c.bb[2]) / 2, (c.bb[1] + c.bb[3]) / 2];
  c.grp = whichCountry(c.rp) || c.isoTag || null;
}

// ---- 按国按级筛 ----
const sel = [];
for (const c of cands) {
  if (!c.grp || !(c.grp in WANT)) continue;
  const lv = LEVEL[c.grp] || LEVEL._d;
  if (!lv.includes(c.al)) continue;
  if (c.a < 1e6) continue;                       // < 1 km²，多为误标
  sel.push(c);
}

// ---- 去重：同一块地同时出现在两级 ----
// 香港在 OSM 里 AL3 和 AL4 各有一份（AL4 那份没有 ISO3166-2 标签），
// 两级都放行就会多出一个单元。代表点几乎重合 + 面积接近 => 判为同一块地，留带 ISO 标签的那个。
{
  const drop = new Set();
  for (let i = 0; i < sel.length; i++) for (let j = i + 1; j < sel.length; j++) {
    const a = sel[i], b = sel[j];
    if (a.grp !== b.grp) continue;
    if (Math.abs(a.rp[0] - b.rp[0]) > 1e-3 || Math.abs(a.rp[1] - b.rp[1]) > 1e-3) continue;
    if (Math.abs(a.a - b.a) / Math.max(a.a, b.a) > 0.05) continue;
    drop.add((a.isoTag ? b : a).fid);
  }
  if (drop.size) console.log("同地重复单元已去重:", drop.size);
  for (let i = sel.length - 1; i >= 0; i--) if (drop.has(sel[i].fid)) sel.splice(i, 1);
}

// ---- 补缺：OSM 少了某个单元时，用下一级并起来重建 ----
// 印尼北苏门答腊省在 OSM 里根本没有 AL4 关系（整个印尼 AL4 只有西/南苏门答腊），
// 是 OSM 自身的缺口。规则：找出没有任何选中单元覆盖的旧单元，
// 收集落在它范围内的下一级候选，合成一个单元。
// 旧多边形只用来判归属，几何仍然全部来自 OSM。
const rebuilds = [];
{
  const covered = new Set();
  for (const u of oldF) {
    for (const c of sel) {
      if (c.grp !== u.properties.grp) continue;
      if (u.rp[0] < c.bb[0] || u.rp[0] > c.bb[2] || u.rp[1] < c.bb[1] || u.rp[1] > c.bb[3]) continue;
      if (contains(c.g, u.rp)) { covered.add(u); break; }
    }
  }
  const selByGrp = {};
  sel.forEach(c => (selByGrp[c.grp] = selByGrp[c.grp] || []).push(c));
  for (const u of oldF) {
    const g = u.properties.grp;
    if (covered.has(u)) continue;
    if ((selByGrp[g] || []).length >= WANT[g]) continue;      // 数量已够，不是缺失
    const lv = String(Number((LEVEL[g] || LEVEL._d)[0]) + 1);
    const parts = cands.filter(c => c.grp === g && c.al === lv && contains(u.geometry, c.rp));
    if (!parts.length) continue;
    rebuilds.push({ grp: g, n: u.properties.n, fids: parts.map(c => c.fid) });
    console.log("重建单元:", g, u.properties.n, "← AL" + lv + " 子单元 " + parts.length + " 个");
    sel.push({ fid: "R" + rebuilds.length, grp: g, al: lv, name: u.properties.n, zh: "",
      isoTag: null, g: parts[0].g, bb: parts[0].bb, a: parts.reduce((s, c) => s + c.a, 0),
      rp: parts[0].rp, rebuiltFrom: parts.map(c => c.fid) });
  }
}

// ---- 中文名 ----
// 优先用 OSM 自己的 name:zh（逐单元权威，中日韩越泰蒙缅覆盖 100%）。
// 没有 name:zh 的才从旧数据继承，且**强制一对一**：
// 旧几何比实际小约 9%，纯按代表点各自就近匹配会交叉串名——印尼的哥伦打洛
// 曾因此拿到中苏拉威西的名字，而报表看不出异常。
for (const c of sel) c.n = c.zh || null;

const byG = {};
sel.forEach(c => (byG[c.grp] = byG[c.grp] || []).push(c));
let inherited = 0, unnamed = 0;
for (const g of Object.keys(byG)) {
  const need = byG[g].filter(c => !c.n);
  if (!need.length) continue;
  const usedNames = new Set(byG[g].map(c => c.n).filter(Boolean));
  const pool = oldF.filter(u => u.properties.grp === g && !usedNames.has(u.properties.n));
  // 所有 (新单元, 旧单元) 配对按代表点距离排序，贪心取，两边各用一次
  const pairs = [];
  need.forEach((c, i) => pool.forEach((u, j) =>
    pairs.push([(c.rp[0] - u.rp[0]) ** 2 + (c.rp[1] - u.rp[1]) ** 2, i, j])));
  pairs.sort((x, y) => x[0] - y[0]);
  const usedC = new Set(), usedU = new Set();
  for (const [, i, j] of pairs) {
    if (usedC.has(i) || usedU.has(j)) continue;
    usedC.add(i); usedU.add(j);
    need[i].n = pool[j].properties.n;
    need[i].inherited = true;
    inherited++;
  }
  need.forEach(c => { if (!c.n) { c.n = c.name; unnamed++; } });
}
console.log("中文名：OSM name:zh", sel.filter(c => c.zh).length, " 从旧数据继承", inherited, " 仍无中文名", unnamed);

// ---- 报表 ----
const byGrp = byG;

console.log("\ngrp   期望  选出  未继承中文名  判定");
let bad = 0, tot = 0;
for (const g of Object.keys(WANT).sort()) {
  const list = byGrp[g] || []; tot += list.length;
  const noZh = list.filter(c => !c.zh && !c.inherited).length;
  const flag = list.length === WANT[g] && noZh === 0 ? "OK"
    : (list.length !== WANT[g] ? (list.length > WANT[g] ? "多" : "少") + Math.abs(list.length - WANT[g]) + " " : "") + (noZh ? noZh + "个待补名" : "");
  if (flag !== "OK") bad++;
  console.log(g.padEnd(6) + String(WANT[g]).padStart(4) + String(list.length).padStart(6) + String(noZh).padStart(12) + "   " + flag);
}
console.log("\n不达标:", bad, "/", Object.keys(WANT).length, "  总单元:", tot, "(旧 612)");

// 断言：同一国家内中文名不得重复。名字重了说明继承逻辑串了，
// 而这种错在报表上只体现为「一切正常」。
{
  let dup = 0;
  for (const g of Object.keys(byGrp)) {
    const ns = byGrp[g].map(c => c.n);
    const d = ns.length - new Set(ns).size;
    if (d) { dup += d; console.log("  !! " + g + " 有 " + d + " 个重名"); }
  }
  console.log(dup ? "重名合计: " + dup + " —— 必须查清再往下走" : "重名检查: 通过");
}

fs.writeFileSync(D + "/picked.json", JSON.stringify(
  sel.map(c => ({ fid: c.fid, grp: c.grp, n: c.n, osm: c.name, zh: c.zh, inherited: !!c.inherited, rebuiltFrom: c.rebuiltFrom || null }))));
console.log("已写出 picked.json");
