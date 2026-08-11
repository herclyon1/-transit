#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""東亜交通 第二批：车站 + 高速公路。

用户：「火车站你都不标么，存在重大缺陷」「高速公路做完的代价是多大？不大的话就一块做了」

为什么分两批：第一批的 osmium 抽取只留了 `railway=rail` 这类**线**上的标签，
车站是标在**点/面**上的（`railway=station`），在抽取那一步就被扔了；
高速当时用户说「后面再考虑」也没留。原始包因为磁盘紧张已经删掉，只能重下一遍，
这一遍两样一起抽（见 ea_transit_dl2.sh）。

  station  railway=station / halt，以及 public_transport=station。
           面（大站在 OSM 里常画成面）取代表点，跟点合到一起按位置去重。
           分三类，跟铁路线的颜色对上：
             sub   地铁站（station=subway 或 subway=yes）
             lrt   轻轨/单轨站
             rail  普通火车站（含高铁站——OSM 没有单独的高铁站标签，
                   而且高铁站几乎都同时办普速，硬分反而错）
           **日本不在这批数据里**：日本用 N02 那份（有事業者、有乗降客数），
           比 OSM 准，两个视图都用它。

  road     highway=motorway（高速）和 highway=trunk（一级公路/快速路）。
           分两层切，motorway 从 z5 起、trunk 从 z7 起——
           trunk 在中国和印度密度极高，跟 motorway 混一层的话低缩放会糊成一片。
           属性全部去掉，好让 tippecanoe 的 --coalesce 把同一条路的上千段合并。
"""
import json, re, sys, os, glob, math, collections, subprocess

D = "/home/user/osm"
EA = D + "/eatr2"
EA3 = D + "/eatr3"      # 第三遍：在建铁路、独立的长途汽车站、有轨电车
W, S_, E, N = 68.0, -12.0, 154.0, 56.0


def tags(s):
    d = {}
    if not s:
        return d
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"', s):
        d[m.group(1)] = m.group(2)
    return d


def rd(p):
    with open(p, encoding="utf-8", errors="replace") as fh:
        for l in fh:
            s = l.replace("\x1e", "").strip()
            if not s:
                continue
            try:
                yield json.loads(s)
            except Exception:
                continue


# 名字：中日港台的 OSM 里，本地 `name` 本来就是汉字，**不能因为有 name:en 就用英文**。
# 上海地铁实测：很多站没有 name:zh，只有 name（汉中路）和 name:en（Hanzhong Road），
# 先前的顺序 name:zh → name:en → name 把它们全写成了英文。
# 规则：name:zh 最优；没有就看本地 name 里有没有汉字，有就用它；
# 都没有（韩国是谚文、东南亚是拉丁/本地文字）再退英文——对中文读者英文比谚文有用。
HAN_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF]")


# OSM 里中国西部/内蒙/西藏的 name 经常是**双语连写**，比如
#   「乌鲁木齐天山国际机场 ئۇرۇمچى تيەنشەن خەلقئارا ئايرودرومى」
# 直接拿来当标注，屏幕上就是一长条中文+维文。既然汉字那一段在，就只留汉字那一段。
OTHER_SCRIPT = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0980-\u09FF"
    r"\u0D80-\u0DFF\u0E00-\u0E7F\u1000-\u109F\u1780-\u17FF"
    r"\u0F00-\u0FFF\u1800-\u18AF\uAC00-\uD7AF]")


def trim_mixed(v):
    """名字里汉字和别的文字连写时，只留汉字开头的那一段。"""
    if not v or not HAN_RE.search(v):
        return v
    m = OTHER_SCRIPT.search(v)
    if not m:
        return v
    return v[:m.start()].strip(" -–—/|·、,，") or v


def name_of(p, t):
    zh = t.get("name:zh") or t.get("name:zh-Hans")
    if zh:
        return trim_mixed(zh)
    loc = p.get("name") or ""
    if HAN_RE.search(loc):
        return trim_mixed(loc)
    return t.get("name:ja") or t.get("name:en") or loc


# 名字兜底：OSM 里同一个东西的名字可能挂在好几个键上。
# 用户：「为什么有这么多元素连名字都没有」——实测中国这一份，
# 机场 1,482 个里 172 个（11.6%）一个 name 标都没有，其中 74 个是军用；
# 火车站 20,330 个里 633 个（3.1%）没有，标签组合是「建筑+车站」，
# 典型的对着卫星图描形状、不知道名字就提交了。真没有的补不出来，
# 但**挂在别的键上的**能捞回来：官方名、别名、外语名、机场的 IATA/ICAO 代码。
NAME_KEYS = ("official_name", "alt_name", "int_name", "short_name",
             "loc_name", "nat_name", "reg_name", "old_name")


def best_name(p, t, code_keys=()):
    zh = t.get("name:zh") or t.get("name:zh-Hans")
    if zh:
        return trim_mixed(zh)
    loc = p.get("name") or t.get("name") or ""
    if HAN_RE.search(loc):
        return trim_mixed(loc)
    for k in ("name:ja", "name:en"):
        if t.get(k):
            return t[k]
    if loc:
        return loc
    # 任何一种语言的 name:xx
    for k in sorted(t):
        if k.startswith("name:") and t[k]:
            return trim_mixed(t[k])
    for k in NAME_KEYS:
        for kk in (k, k + ":zh", k + ":en"):
            if t.get(kk):
                return trim_mixed(t[kk])
    # 机场退到 IATA/ICAO 代码——总比一块没名字的色块强
    for k in code_keys:
        if t.get(k):
            return t[k].strip()
    return ""


def cent(g):
    ty = g["type"]
    c = g["coordinates"]
    if ty == "Point":
        return c
    if ty == "LineString":
        return c[len(c) // 2]
    if ty == "MultiLineString":
        c = [x for l in c for x in l]
        return c[len(c) // 2]
    if ty == "Polygon":
        c = c[0]
    elif ty == "MultiPolygon":
        c = c[0][0]
    else:
        return None
    return [sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)]


o_st = open(D + "/ea_station.geojsonl", "w")
o_mw = open(D + "/ea_motorway.geojsonl", "w")
o_tk = open(D + "/ea_trunk.geojsonl", "w")
o_con = open(D + "/ea_rail_con.geojsonl", "w")
o_tram = open(D + "/ea_rail_tram.geojsonl", "w")
cnt = collections.Counter()
sta = {}

pbfs = sorted(glob.glob(EA + "/*.pbf")) + sorted(glob.glob(EA3 + "/*.pbf"))
if not pbfs:
    sys.exit("没有 eatr2/*.pbf，先跑 ea_transit_dl2.sh")
TMP = EA + "/_x.geojsonl"

for pb in pbfs:
    country = os.path.basename(pb)[:-4]
    subprocess.run(["osmium", "export", pb, "-f", "geojsonseq",
                    "--geometry-types=point,linestring,polygon",
                    "-o", TMP, "--overwrite", "-u", "type_id"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    c0 = sum(cnt.values())
    for f in rd(TMP):
        p = f["properties"]
        g = f.get("geometry")
        if not g:
            continue
        t = tags(p.get("other_tags"))
        t.update({k: v for k, v in p.items() if k != "other_tags" and v is not None})
        pt = cent(g)
        if not pt or not (W <= pt[0] <= E and S_ <= pt[1] <= N):
            continue

        hw = t.get("highway")
        if hw in ("motorway", "trunk") and "Line" in g["type"]:
            (o_mw if hw == "motorway" else o_tk).write(
                json.dumps({"type": "Feature", "properties": {},
                            "geometry": g}, ensure_ascii=False) + "\n")
            cnt["road_" + hw] += 1
            continue

        # 在建铁路 / 有轨电车 / 缆索铁路（第三遍才下到的）
        rw = t.get("railway")
        if rw in ("construction", "tram", "funicular") and "Line" in g["type"]:
            if t.get("disused") or t.get("abandoned"):
                continue
            if rw == "construction":
                # 在建的是不是铁路？construction=rail/subway/... 说了算；没写就当铁路
                c = (t.get("construction") or "rail")
                if c not in ("rail", "subway", "light_rail", "monorail",
                             "narrow_gauge", "tram", "yes"):
                    continue
                o_con.write(json.dumps({"type": "Feature", "properties": {},
                                        "geometry": g}, ensure_ascii=False) + "\n")
                cnt["rail_construction"] += 1
            else:
                o_tram.write(json.dumps({"type": "Feature", "properties": {},
                                         "geometry": g}, ensure_ascii=False) + "\n")
                cnt["rail_" + rw] += 1
            continue

        # 車站分六类。用户：「长途汽车站可以保留啊，这个是细节补充，
        # 我只是希望能有标签名字而已」「在建铁路可以画啊，标注出来就行」。
        #   rail/sub/lrt  在营的火车站/地铁站/轻轨站
        #   con           在建的车站（跟在建线路一起画成虚线色）
        #   bus           长途汽车站（amenity=bus_station）
        #   aerial        索道站（aerialway=station）
        # `public_transport=station` 单独不算火车站——汽车站、索道站也打这个标，
        # 所以要么明确 railway=station/halt，要么它同时带着轨道类的标。
        amen = t.get("amenity")
        aer = t.get("aerialway")
        rwn = t.get("railway")
        nm = best_name(p, t)
        dead = t.get("disused") or t.get("abandoned")
        constr = bool(t.get("construction") or t.get("construction:railway")
                      or (t.get("station") or "") == "construction"
                      or "在建" in nm or "建設中" in nm)
        railish = (rwn in ("station", "halt") or
                   (t.get("public_transport") == "station" and
                    (rwn or t.get("train") == "yes" or t.get("subway") == "yes"
                     or t.get("light_rail") == "yes" or t.get("monorail") == "yes")))
        if amen == "bus_station":
            k = "bus"
        elif aer == "station":
            k = "aerial"
        elif railish and not dead and not t.get("highway"):
            if constr:
                k = "con"
            else:
                st = (t.get("station") or "").lower()
                if st == "subway" or t.get("subway") == "yes":
                    k = "sub"
                elif st in ("light_rail", "monorail", "tram") or \
                        t.get("light_rail") == "yes" or t.get("monorail") == "yes":
                    k = "lrt"
                else:
                    k = "rail"
        else:
            continue
        # 同一个站常常又有点又有面（站房、站台各一个），先按 250m 网格 + 同名去重
        key = (nm, k if k in ("bus", "aerial") else "r",
               round(pt[0] * 400), round(pt[1] * 400))
        if key not in sta:
            sta[key] = (nm, k, pt)
        elif sta[key][1] == "rail" and k not in ("rail", "con"):
            sta[key] = (nm, k, pt)
        continue
    print("  %-28s +%d" % (country, sum(cnt.values()) - c0), flush=True)

# 同名 600m 以内合成一个：OSM 里一个站常常站房一个点、站台一个面、
# 出入口再一个点，位置差个两三百米。250m 网格切不干净（上海马戏城实测出了两个）。
_items = list(sta.values())
_R = 600 / 111000.0
_grid = collections.defaultdict(list)
for i, (n_, k_, pt_) in enumerate(_items):
    _grid[(int(pt_[0] / _R), int(pt_[1] / _R))].append(i)
_par = list(range(len(_items)))


def _find(a):
    while _par[a] != a:
        _par[a] = _par[_par[a]]
        a = _par[a]
    return a


for i, (n_, k_, pt_) in enumerate(_items):
    if not n_:
        continue                       # 无名的不合并，位置本来就代表不同设施
    gx, gy = int(pt_[0] / _R), int(pt_[1] / _R)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in _grid.get((gx + dx, gy + dy), ()):
                if j <= i or _items[j][0] != n_:
                    continue
                # 汽车站和火车站可能同名同址（「XX站」），但不是一个东西，不能合
                bus_i = k_ in ("bus", "aerial")
                bus_j = _items[j][1] in ("bus", "aerial")
                if bus_i != bus_j:
                    continue
                q = _items[j][2]
                if math.hypot((q[0] - pt_[0]) * 85, (q[1] - pt_[1]) * 111) > 0.6:
                    continue
                ra, rb = _find(i), _find(j)
                if ra != rb:
                    _par[rb] = ra

_cl = collections.defaultdict(list)
for i in range(len(_items)):
    _cl[_find(i)].append(i)
merged = []
for idx in _cl.values():
    n_ = _items[idx[0]][0]
    ks = [_items[i][1] for i in idx]
    if "bus" in ks:
        k_ = "bus"
    elif "aerial" in ks:
        k_ = "aerial"
    elif "sub" in ks:
        k_ = "sub"
    elif "lrt" in ks:
        k_ = "lrt"
    elif "rail" in ks:
        k_ = "rail"
    else:
        k_ = "con"
    x = sum(_items[i][2][0] for i in idx) / len(idx)
    y = sum(_items[i][2][1] for i in idx) / len(idx)
    merged.append((n_, k_, [x, y]))
print("车站按同名 600m 合并：%d → %d" % (len(_items), len(merged)), flush=True)

for nm, k, pt in merged:
    o_st.write(json.dumps({"type": "Feature", "properties": {"n": nm, "k": k},
                           "geometry": {"type": "Point",
                                        "coordinates": [round(pt[0], 5), round(pt[1], 5)]}},
                          ensure_ascii=False) + "\n")
    cnt["station_" + k] += 1
for f in (o_st, o_mw, o_tk, o_con, o_tram):
    f.close()
if os.path.exists(TMP):
    os.remove(TMP)
print("\n统计：")
for k in sorted(cnt):
    print("  %-14s %8d" % (k, cnt[k]))
named = sum(1 for nm, k, pt in merged if nm)
print("  车站里有名字的  %8d / %d" % (named, len(merged)))
