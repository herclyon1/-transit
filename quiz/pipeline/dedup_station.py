# -*- coding: utf-8 -*-
"""N02 的駅是**按线路**给的：難波 有 4 条记录（大阪メトロ 御堂筋/四つ橋/千日前 + 南海本線），
   直接画就是同一个站上叠 4 个点。用户在真机上一眼看出来。
   旧的「車站可達性」项目是拿去重后的 station_id 画的，并且渲染时还按格子稀释——照抄这个思路。

   两步合并：
   1) N02_005g（同一駅グループコード）—— 官方给的，先按它合
   2) 同名且 500m 以内 —— 跨事業者的同名站（南海難波 vs メトロなんば）官方分属不同 group，
      但在图上就是一个站，按空间近邻再合一次
   合并后给每站记 lines（线路数），渲染时按缩放级别用它稀释。
"""
import json, math, collections

d = json.load(open("n02/UTF-8/N02-24_Station.geojson", encoding="utf-8"))
fs = d["features"]

def mid(g):
    cs = g["coordinates"]
    pts = cs if g["type"] == "LineString" else [c for p in cs for c in p]
    xs = [c[0] for c in pts]; ys = [c[1] for c in pts]
    return ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2)

# 1) 按官方 group 合
byg = collections.defaultdict(list)
for f in fs:
    p = f["properties"]
    byg[p.get("N02_005g") or ("c:"+str(p.get("N02_005c")))].append(f)

nodes = []
for k, group in byg.items():
    pts = [mid(f["geometry"]) for f in group]
    x = sum(p[0] for p in pts)/len(pts); y = sum(p[1] for p in pts)/len(pts)
    nodes.append({"x":x,"y":y,
                  "n":group[0]["properties"].get("N02_005"),
                  "lines":{(f["properties"].get("N02_004"),f["properties"].get("N02_003")) for f in group},
                  "cls":{f["properties"].get("N02_002") for f in group}})
print("按官方 group 合并后:", len(nodes))

# 2) 同名 + 500m 以内再合
R = 0.0055   # ≈ 500m
grid = collections.defaultdict(list)
def gk(x,y): return (int(x/R), int(y/R))
for i,nd in enumerate(nodes): grid[gk(nd["x"],nd["y"])].append(i)

parent = list(range(len(nodes)))
def find(a):
    while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
    return a
def union(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: parent[rb]=ra

for i,nd in enumerate(nodes):
    cx,cy = gk(nd["x"],nd["y"])
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            for j in grid.get((cx+dx,cy+dy),()):
                if j<=i: continue
                o=nodes[j]
                if o["n"]!=nd["n"]: continue
                if math.hypot((o["x"]-nd["x"])*0.82,(o["y"]-nd["y"])) > R: continue
                union(i,j)

merged = collections.defaultdict(list)
for i in range(len(nodes)): merged[find(i)].append(i)
print("同名近邻再合并后:", len(merged))

out=[]
for root, idxs in merged.items():
    xs=[nodes[i]["x"] for i in idxs]; ys=[nodes[i]["y"] for i in idxs]
    lines=set(); cls=set()
    for i in idxs: lines |= nodes[i]["lines"]; cls |= nodes[i]["cls"]
    # 显示等级：线路条数（越多越是枢纽）
    rank=len(lines)
    ops=sorted({o for o,_ in lines})
    out.append({"type":"Feature","properties":{
        "n":nodes[idxs[0]]["n"],
        "rank":rank,
        "ln":"、".join(sorted({l for _,l in lines}))[:80],
        "op":"、".join(ops)[:60]},
        "geometry":{"type":"Point","coordinates":[sum(xs)/len(xs), sum(ys)/len(ys)]}})

with open("tr_station.geojsonl","w",encoding="utf-8") as f:
    for x in out: f.write(json.dumps(x,ensure_ascii=False)+"\n")
print("最终駅数:", len(out))
rk=collections.Counter(x["properties"]["rank"] for x in out)
print("按线路条数分布:", sorted(rk.items())[:8], "... 最多", max(rk))
for nm in ["難波","梅田","新宿","東京","渋谷"]:
    hit=[x for x in out if x["properties"]["n"]==nm]
    print("  %s → %d 个点，线路 %s"%(nm,len(hit), hit[0]["properties"]["ln"][:60] if hit else "-"))
