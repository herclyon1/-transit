# -*- coding: utf-8 -*-
"""公共交通图层。数据全部取自国土交通省 国土数値情報（官方）：
   N02-24 鉄道（区間 21,932 / 駅）、C28-21 空港、N09-12 定期旅客航路。
   分类不靠猜，是按 N02 的「鉄道区分 × 事業者種別」交叉表实测出来的：
     (11,1)=新幹線  (11,2)=JR在来線  (12,3)=公営地下鉄  (12,4)=民営  (12,5)=三セク
     (21,*)=軌道（路面電車） (13,*)=鋼索（ケーブル） (15/16/22/23/24/25)=モノレール・新交通
   两处必须特判，否则会分错：
     ・大阪メトロ（大阪市高速電気軌道）法律上是「軌道」，混在路面電車里
     ・札幌市営地下鉄是「案内軌条式(16)」，不在(12,3)里
"""
import json, glob, sys

SUBWAY_OPS = {"東京地下鉄","大阪市高速電気軌道","東京都","名古屋市","横浜市",
              "福岡市","京都市","神戸市","仙台市","札幌市"}
# 这三条属于上述事業者但不是地下鉄，必须排除
NOT_SUBWAY = {("東京都","荒川線"),("東京都","日暮里・舎人ライナー"),
              ("大阪市高速電気軌道","南港ポートタウン線")}
MONO = {"15","16","22","23","24","25"}

def cls_of(p):
    k, t = p["N02_001"], p["N02_002"]
    op, ln = p.get("N02_004") or "", p.get("N02_003") or ""
    if (k,t)==("11","1"): return "shinkansen"
    if (k,t)==("11","2"): return "jr"
    if op in SUBWAY_OPS and (op,ln) not in NOT_SUBWAY and k not in ("24",):
        return "subway"
    if k=="21": return "tram"
    if k in MONO: return "mono"
    if k in ("13","14"): return "cable"
    if t=="4": return "private"
    if t=="5": return "sector3"
    if t=="3": return "public"
    return "other"

out = {}
def w(name, feats):
    fn = name+".geojsonl"
    with open(fn,"w",encoding="utf-8") as f:
        for x in feats: f.write(json.dumps(x,ensure_ascii=False)+"\n")
    out[name]=len(feats); return fn

# ── 鉄道 ──
d = json.load(open("n02/UTF-8/N02-24_RailroadSection.geojson",encoding="utf-8"))
import collections
cc = collections.Counter()
rail=[]
for f in d["features"]:
    p=f["properties"]; c=cls_of(p); cc[c]+=1
    rail.append({"type":"Feature","properties":{
        "cls":c,"n":p.get("N02_003"),"op":p.get("N02_004")},"geometry":f["geometry"]})
w("tr_rail",rail)
print("鉄道区間分类:", dict(sorted(cc.items(), key=lambda x:-x[1])))

# ── 駅 ──
d = json.load(open("n02/UTF-8/N02-24_Station.geojson",encoding="utf-8"))
print("駅属性:", list(d["features"][0]["properties"].keys()))
st=[]
for f in d["features"]:
    p=f["properties"]
    st.append({"type":"Feature","properties":{
        "cls":cls_of(p),"n":p.get("N02_005"),"line":p.get("N02_003"),"op":p.get("N02_004")},
        "geometry":f["geometry"]})
w("tr_station",st)

# ── 空港 ──
d = json.load(open("c28/UTF-8/C28-21_Airport.geojson",encoding="utf-8"))
air=[]
for f in d["features"]:
    p=f["properties"]; nm=p.get("C28_005") or ""; t=p.get("C28_003")
    kind = "kokusai" if "国際" in nm else ("kyoten" if t in (1,2,3) else "chiho")
    air.append({"type":"Feature","properties":{"n":nm,"kind":kind,"t":t},"geometry":f["geometry"]})
w("tr_air",air)
print("空港:", collections.Counter(a["properties"]["kind"] for a in air))

# ── 航路 ──
fer=[]
lo=hi=None
for line in open("n09.geojson",encoding="utf-8"):
    s=line.replace("\x1e","").strip()
    if not s: continue
    f=json.loads(s); p=f["properties"]
    g=f["geometry"]
    if not g: continue
    xs=[c[0] for c in g["coordinates"]] if g["type"]=="LineString" else [c[0] for part in g["coordinates"] for c in part]
    lo = min(xs) if lo is None else min(lo,min(xs)); hi = max(xs) if hi is None else max(hi,max(xs))
    fer.append({"type":"Feature","properties":{
        "n":p.get("N09_006"),"op":p.get("N09_009")},"geometry":g})
w("tr_ferry",fer)
print("航路经度范围 %.3f ~ %.3f（应在 122~154 之间才是经纬度）"%(lo,hi))
print("产出:", out)
