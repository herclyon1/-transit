// 最小 TopoJSON 解码 + 点在多边形判定 + 面积/代表点。
// 不引外部依赖：容器是临时的，装包这一步以后一定会有人跳过。
"use strict";

function decodeArcs(topo) {
  const { scale: s, translate: t } = topo.transform || {};
  return topo.arcs.map(arc => {
    let x = 0, y = 0;
    return arc.map(p => {
      if (topo.transform) { x += p[0]; y += p[1]; return [x * s[0] + t[0], y * s[1] + t[1]]; }
      return [p[0], p[1]];
    });
  });
}

function arcLine(arcs, i) {
  return i < 0 ? arcs[~i].slice().reverse() : arcs[i];
}

function ringOf(arcs, idxs) {
  const out = [];
  idxs.forEach((i, k) => {
    const line = arcLine(arcs, i);
    for (let j = k ? 1 : 0; j < line.length; j++) out.push(line[j]);
  });
  return out;
}

function geomOf(arcs, g) {
  if (g.type === "Polygon") return { type: "Polygon", coordinates: g.arcs.map(r => ringOf(arcs, r)) };
  if (g.type === "MultiPolygon") return { type: "MultiPolygon", coordinates: g.arcs.map(p => p.map(r => ringOf(arcs, r))) };
  if (g.type === "LineString") return { type: "LineString", coordinates: ringOf(arcs, g.arcs) };
  if (g.type === "MultiLineString") return { type: "MultiLineString", coordinates: g.arcs.map(l => ringOf(arcs, l)) };
  return null;
}

function topoToFeatures(topo, layer) {
  const arcs = decodeArcs(topo);
  return topo.objects[layer].geometries.map(g => ({
    type: "Feature", properties: g.properties || {}, geometry: geomOf(arcs, g)
  }));
}

// ---- 几何工具 ----
const R = 6371008.8, rad = Math.PI / 180;

function ringArea(r) {
  let s = 0;
  for (let i = 0, n = r.length, j = n - 1; i < n; j = i++) {
    const [x1, y1] = r[j], [x2, y2] = r[i];
    s += (x2 - x1) * rad * (2 + Math.sin(y1 * rad) + Math.sin(y2 * rad));
  }
  return s * R * R / 2;
}

function area(g) {
  if (!g) return 0;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  return polys.reduce((a, p) => a + p.reduce((b, r, i) => b + (i ? -Math.abs(ringArea(r)) : Math.abs(ringArea(r))), 0), 0);
}

function bbox(g) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  (function walk(c) {
    if (typeof c[0] === "number") {
      if (c[0] < x0) x0 = c[0]; if (c[0] > x1) x1 = c[0];
      if (c[1] < y0) y0 = c[1]; if (c[1] > y1) y1 = c[1];
    } else c.forEach(walk);
  })(g.coordinates);
  return [x0, y0, x1, y1];
}

function pipRing(pt, ring) {
  let inside = false;
  for (let i = 0, n = ring.length, j = n - 1; i < n; j = i++) {
    const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
    if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function contains(g, pt) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  for (const p of polys) {
    if (!pipRing(pt, p[0])) continue;
    let hole = false;
    for (let i = 1; i < p.length; i++) if (pipRing(pt, p[i])) { hole = true; break; }
    if (!hole) return true;
  }
  return false;
}

// 代表点：取最大外环的重心，若落在洞里或环外，退回环上顶点的平均再退回首顶点。
function repPoint(g) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  if (!polys.length) return null;
  let best = null, bestA = -1;
  for (const p of polys) { const a = Math.abs(ringArea(p[0])); if (a > bestA) { bestA = a; best = p; } }
  const ring = best[0];
  let cx = 0, cy = 0;
  for (const v of ring) { cx += v[0]; cy += v[1]; }
  const c = [cx / ring.length, cy / ring.length];
  if (contains(g, c)) return c;
  // 重心在洞里或凹形之外：沿环顶点找一个确实在内部的点
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i], b = ring[(i + 1) % ring.length];
    const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const probe = [m[0] + (c[0] - m[0]) * 1e-3, m[1] + (c[1] - m[1]) * 1e-3];
    if (contains(g, probe)) return probe;
  }
  return c;
}

function segStats(g) {
  const out = [];
  (function walk(c) {
    if (typeof c[0][0] === "number") {
      for (let i = 1; i < c.length; i++) {
        const a = c[i - 1], b = c[i];
        const dy = (b[1] - a[1]) * rad, dx = (b[0] - a[0]) * rad * Math.cos((a[1] + b[1]) / 2 * rad);
        out.push(Math.hypot(dx, dy) * R);
      }
    } else c.forEach(walk);
  })(g.coordinates);
  return out;
}

module.exports = { topoToFeatures, area, bbox, contains, repPoint, segStats, ringArea };
