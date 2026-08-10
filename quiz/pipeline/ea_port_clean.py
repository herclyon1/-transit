#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""东亚的港口/口岸点清洗：把不挨着水的「港」扔掉，同名的合并。

用户：「乌鲁木齐底下两个点是什么，完全不显示名字」

查出来是坐标 87.61,43.75 的两个 `industrial=port`——实际是**乌鲁木齐国际陆港区**
（中欧班列的集装箱堆场）。OSM 里「港」这个标签被人用在了内陆铁路货场上，
我照单全收，于是沙漠中间冒出两个「港口」，而且没名字。
旁边「西域轻工基地国家二类口岸」标了两遍，是去重半径太小（按 110m 合并，
那两个点隔了 105m），差一点点没合上。

两条规则：

1. **港必须挨着水**。判据是：点落在海里（不在任何陆地多边形内）→ 一定是；
   落在陆地里的话，离陆地边界（＝海岸线）2km 以内、或者离已绘制的水体 1km 以内
   才算数。内陆货场离海岸线上千公里，一刀切掉。
   ——不用「有没有名字」当判据：真港口没名字的多得是，
   而这个陆港区就算哪天有人补上名字，它也不该出现在港口层里。

2. **同名 1km 内合成一个**。跨越 110m 网格的重复标注（口岸常见，
   一个口岸的关口和货场各打一个点）就不会写两遍名字了。
"""
import json, math, collections, subprocess, os

D = "/home/user/osm"
KX, KY = 85.0, 111.0            # 东亚中纬度，1° 约合多少 km


def rd(p):
    for l in open(p):
        s = l.replace("\x1e", "").strip()
        if s:
            yield json.loads(s)


ports = list(rd(D + "/ea_port.geojsonl"))
bcs = list(rd(D + "/ea_bc.geojsonl"))
print("清洗前：港口 %d、口岸 %d" % (len(ports), len(bcs)), flush=True)

# ── 1) 港必须挨着水 ──
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

# 只取港口点周围的陆地块，整份 143,024 块全读进来没必要
xs = [f["geometry"]["coordinates"][0] for f in ports]
ys = [f["geometry"]["coordinates"][1] for f in ports]
subprocess.run(["ogr2ogr", "-f", "GeoJSONSeq", D + "/_pl.geojsonl",
                D + "/region_land.gpkg", "land",
                "-spat", str(min(xs) - .5), str(min(ys) - .5),
                str(max(xs) + .5), str(max(ys) + .5)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
land, bnd = [], []
for f in rd(D + "/_pl.geojsonl"):
    g = shape(f["geometry"])
    if not g.is_valid:
        g = g.buffer(0)
    land.append(g)
    bnd.append(g.boundary)
os.remove(D + "/_pl.geojsonl")
tl, tb = STRtree(land), STRtree(bnd)
print("陆地块 %d" % len(land), flush=True)

# 水体：只留**够大的（≥2 km²）**。第一版卡 0.1 km² 不够——
# 乌鲁木齐陆港区里正好有个 0.22 km² 的景观湖/沉淀池贴着货场，
# 那种 470m 见方的水塘停不了船，却把整条规则绕过去了。
# 2 km² 这条线放得过洞庭、鄱阳、天池（4.9 km²）这类真能通航的湖。
wat = []
for f in rd(D + "/water_all3.geojsonl"):
    try:
        g = shape(f["geometry"])
    except Exception:
        continue
    if g.area * KX * KY < 2.0:
        continue
    if not g.is_valid:
        g = g.buffer(0)
    wat.append(g)
tw = STRtree(wat)
print("够大的水体 %d 块" % len(wat), flush=True)

SEA_KM, LAKE_KM = 2.0, 1.0
DEG_SEA = SEA_KM / KY                       # 纬度方向的度数，够当查询半径用
DEG_LAKE = LAKE_KM / KY
keep, drop = [], collections.Counter()
for f in ports:
    x, y = f["geometry"]["coordinates"]
    p = Point(x, y)
    inland = any(land[i].contains(p) for i in tl.query(p))
    if not inland:
        keep.append(f)                      # 落在海里，一定是港
        continue
    ok = False
    box = p.buffer(DEG_SEA)
    for i in tb.query(box):
        if bnd[i].distance(p) * KY < SEA_KM:
            ok = True
            break
    if not ok:
        box = p.buffer(DEG_LAKE)
        for i in tw.query(box):
            if wat[i].distance(p) * KY < LAKE_KM:
                ok = True
                break
    if ok:
        keep.append(f)
    else:
        drop[f["properties"].get("n") or "(无名)"] += 1
print("离水太远被扔掉的港 %d 个，前几个：%s"
      % (sum(drop.values()), drop.most_common(6)), flush=True)


# ── 2) 同名 1km 内合成一个 ──
def merge(fs, km=1.0):
    grid = collections.defaultdict(list)
    R = km / KY
    for i, f in enumerate(fs):
        x, y = f["geometry"]["coordinates"]
        grid[(int(x / R), int(y / R))].append(i)
    par = list(range(len(fs)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for i, f in enumerate(fs):
        x, y = f["geometry"]["coordinates"]
        n = f["properties"].get("n") or ""
        if not n:
            continue                        # 无名的不合并，位置本来就代表不同设施
        gx, gy = int(x / R), int(y / R)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j <= i or (fs[j]["properties"].get("n") or "") != n:
                        continue
                    x2, y2 = fs[j]["geometry"]["coordinates"]
                    if math.hypot((x2 - x) * KX, (y2 - y) * KY) > km:
                        continue
                    ra, rb = find(i), find(j)
                    if ra != rb:
                        par[rb] = ra
    cl = collections.defaultdict(list)
    for i in range(len(fs)):
        cl[find(i)].append(i)
    out = []
    for idx in cl.values():
        f = dict(fs[idx[0]])
        cx = sum(fs[i]["geometry"]["coordinates"][0] for i in idx) / len(idx)
        cy = sum(fs[i]["geometry"]["coordinates"][1] for i in idx) / len(idx)
        # 商港优先于渡轮码头：同名同址两种标法都有时，按更重的那个画
        ks = {fs[i]["properties"].get("k") for i in idx}
        f = {"type": "Feature",
             "properties": dict(fs[idx[0]]["properties"],
                                **({"k": "port"} if "port" in ks else {})),
             "geometry": {"type": "Point", "coordinates": [round(cx, 5), round(cy, 5)]}}
        out.append(f)
    return out


keep2 = merge(keep)
bcs2 = merge(bcs)
print("同名合并：港口 %d → %d，口岸 %d → %d"
      % (len(keep), len(keep2), len(bcs), len(bcs2)))

for path, fs in ((D + "/ea_port.geojsonl", keep2), (D + "/ea_bc.geojsonl", bcs2)):
    with open(path, "w") as o:
        for f in fs:
            o.write(json.dumps(f, ensure_ascii=False) + "\n")

# 复查用户报的那两个点
print("复查乌鲁木齐一带（85–91E, 41–45N）剩下的港/口岸：")
for tag, fs in (("港", keep2), ("口岸", bcs2)):
    for f in fs:
        x, y = f["geometry"]["coordinates"]
        if 85 < x < 91 and 41 < y < 45:
            print("   %s %.4f,%.4f %r" % (tag, x, y, f["properties"].get("n") or "(无名)"))
