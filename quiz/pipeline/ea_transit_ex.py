#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""東亜交通：把 eatr/*.pbf 里抽出来的东西整理成五份 geojsonl。

用户点的名：「东亚的铁路，港口、口岸/边境检查站，机场，轮渡航路都加上。
高速公路的等我后面考虑一下。」

分五层，每层的取舍理由写在下面：

  rail   铁路。OSM 的 railway=* 打在 **way** 上（关系只是把 way 归成线路），
         所以只取 way 就够，不会漏。分四类，因为画法要分轻重：
           hs      高速铁路 —— highspeed=yes 或 usage=highspeed，或者
                   maxspeed>=200。中国的高铁在 OSM 里这三个标至少中一个。
           rail    普通铁路（干线/支线/窄轨）
           sub     地铁 subway
           lrt     轻轨/单轨 light_rail, monorail
         过滤掉 service=yard/siding/spur（编组场和岔线），不然大站附近糊成一团。
         也过滤 usage=industrial（厂矿专用线）和 disused/abandoned。

  air    机场。国际/非国际按用户要求分开标：
           intl=1  aerodrome:type 含 international，或者有 IATA 码且
                   aerodrome:type 不是 military/private
           intl=0  其余（国内/通用/军民合用）——「非国际的就特别标注一下，都画上去」
         军用（aerodrome:type=military）单独一类 mil，不跟民航混。
         面用面，只有点的就出点，两边都有的以面为准（按名字去重）。

  ferry  轮渡航路。跟日本那边一个道理：**只有 OSM 的 route=ferry 是真航迹**，
         官方数据里那种两点直线不能用。way 上直接带 route=ferry。

  port   港口。harbour=yes / industrial=port / seamark:type=harbour /
         amenity=ferry_terminal 四种标法混着用，合成一层，出代表点。

  bc     口岸 / 边境检查站。barrier=border_control，点和线都有，统一出点。

名字：优先 name:zh（东亚这几个国家中文名在 OSM 里覆盖不错），
      没有就 name:en，再没有就本地 name。三个都没有就不出标注（但几何照画）。
"""
import json, re, sys, os, glob, math, collections

D = "/home/user/osm"
EA = D + "/eatr"


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


def nm(p, t):
    return (t.get("name:zh") or t.get("name:zh-Hans") or t.get("name:ja")
            or t.get("name:en") or p.get("name") or "")


def glen(g):
    """线长（km）。低缩放要先给长线路让位——瓦片放不下所有东西的时候，
    按密度随机丢会把跨海航路丢掉、留下一堆河渡口，那样低缩放就废了。"""
    ls = ([g["coordinates"]] if g["type"] == "LineString"
          else g["coordinates"] if g["type"] == "MultiLineString" else [])
    s = 0.0
    for c in ls:
        for i in range(1, len(c)):
            dx = (c[i][0] - c[i - 1][0]) * 111.0 * math.cos(math.radians(c[i][1]))
            dy = (c[i][1] - c[i - 1][1]) * 111.0
            s += math.hypot(dx, dy)
    return s


def cent(g):
    """代表点：线取中点顶点，面取顶点平均。够用了，不值得为它引 shapely。"""
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


# 東亜视图的取景范围。澳新那个包是为了太平洋岛国顺带下的，
# 主体离得太远，超出这个框的一律不要，不然瓦片白白胖一圈。
W, S_, E, N = 68.0, -12.0, 154.0, 56.0


def inbox(pt):
    return pt and W <= pt[0] <= E and S_ <= pt[1] <= N


# 「国际」在本区各语言里的写法。只要机场名里出现其中之一就算国际机场。
INTL_RE = re.compile(
    "|".join([r"[Ii]nternational", r"[Ii]nternasional", r"[Ii]nternacional",
              "国际", "國際", "国際", "국제", r"[Qq]uốc tế", "นานาชาติ",
              "အပြည်ပြည်ဆိုင်ရာ", "আন্তর্জাতিক", "अंतर्राष्ट्रीय", "अन्तर्राष्ट्रिय",
              "ජාත්‍යන්තර", "អន្តរជាតិ", "ສາກົນ"]))

RAIL = {"rail", "subway", "light_rail", "monorail", "narrow_gauge"}
BADSVC = {"yard", "siding", "spur", "crossover"}

o_rail = open(D + "/ea_rail.geojsonl", "w")
o_air = open(D + "/ea_air.geojsonl", "w")
o_airp = open(D + "/ea_airpt.geojsonl", "w")
o_fer = open(D + "/ea_ferry.geojsonl", "w")
o_port = open(D + "/ea_port.geojsonl", "w")
o_bc = open(D + "/ea_bc.geojsonl", "w")

cnt = collections.Counter()
airs = {}          # 名字 → 最好的一条（面优先）
ports = {}
bcs = {}

# 磁盘只剩 4GB，而 china 一个包导成 geojson 就 274MB，20 个国家同时摊开放不下。
# 所以「导一个 → 读一个 → 立刻删」，峰值只有最大那一个。
import subprocess
pbfs = sorted(glob.glob(EA + "/*.pbf"))
if not pbfs:
    sys.exit("没有 eatr/*.pbf，先跑 ea_transit_dl.sh")
TMP = EA + "/_x.geojsonl"

for pb in pbfs:
    country = os.path.basename(pb)[:-4]
    subprocess.run(["osmium", "export", pb, "-f", "geojsonseq",
                    "--geometry-types=point,linestring,polygon",
                    "-o", TMP, "--overwrite", "-u", "type_id"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fp = TMP
    c0 = sum(cnt.values())
    for f in rd(fp):
        p = f["properties"]
        g = f.get("geometry")
        if not g:
            continue
        t = tags(p.get("other_tags"))
        t.update({k: v for k, v in p.items() if k != "other_tags" and v is not None})
        pt = cent(g)
        if not inbox(pt):
            continue

        # ── 铁路 ──
        rw = t.get("railway")
        if rw in RAIL and "Line" in g["type"]:
            if t.get("service") in BADSVC or t.get("usage") == "industrial":
                continue
            if t.get("disused") or t.get("abandoned") or t.get("construction"):
                continue
            ms = t.get("maxspeed") or ""
            m = re.match(r"(\d+)", ms)
            fast = (t.get("highspeed") == "yes" or t.get("usage") == "highspeed"
                    or (m and int(m.group(1)) >= 200))
            k = ("hs" if fast else
                 "sub" if rw == "subway" else
                 "lrt" if rw in ("light_rail", "monorail") else "rail")
            o_rail.write(json.dumps({"type": "Feature",
                                     "properties": {"k": k, "L": round(glen(g), 1)},
                                     "geometry": g}, ensure_ascii=False) + "\n")
            cnt["rail_" + k] += 1
            continue

        # ── 轮渡 ──
        if t.get("route") == "ferry" and "Line" in g["type"]:
            o_fer.write(json.dumps({"type": "Feature",
                                    "properties": {"n": nm(p, t), "L": round(glen(g), 1)},
                                    "geometry": g}, ensure_ascii=False) + "\n")
            cnt["ferry"] += 1
            continue

        # ── 机场 ──
        if t.get("aeroway") == "aerodrome":
            at = (t.get("aerodrome:type") or t.get("aerodrome") or "").lower()
            iata = (t.get("iata") or "").strip()
            name = nm(p, t)
            # aerodrome:type 这个标在东亚很不可靠——北京首都国际机场标的是 public，
            # 中印两国加起来只有 100 个标了 international。所以再看名字：
            # 各国的机场名里「国际」二字几乎不会漏（这是官方定名的一部分）。
            alln = " ".join(filter(None, [name, p.get("name"), t.get("name:en"),
                                          t.get("name:zh"), t.get("official_name")]))
            byname = bool(INTL_RE.search(alln))
            if at in ("military", "military/private", "private/military"):
                kind = "mil"
            elif "international" in at or byname:
                kind = "intl"
            else:
                kind = "dom"
            key = (name or "") + "|" + (iata or "") + "|%.2f,%.2f" % (pt[0], pt[1])
            poly = "Polygon" in g["type"]
            old = airs.get(key)
            if old is None or (poly and not old[0]):
                airs[key] = (poly, name, kind, iata, g, pt)
            continue

        # ── 港口 ──
        if (t.get("harbour") == "yes" or t.get("industrial") == "port"
                or t.get("seamark:type") == "harbour"
                or t.get("amenity") == "ferry_terminal"):
            k = "ft" if t.get("amenity") == "ferry_terminal" else "port"
            name = nm(p, t)
            key = "%.3f,%.3f" % (pt[0], pt[1])
            if key not in ports or (name and not ports[key][0]):
                ports[key] = (name, k, pt)
            continue

        # ── 口岸 ──
        if t.get("barrier") == "border_control":
            key = "%.3f,%.3f" % (pt[0], pt[1])
            bcs.setdefault(key, (nm(p, t), pt))
            continue
    print("  %-28s +%d" % (country, sum(cnt.values()) - c0), flush=True)

for poly, name, kind, iata, g, pt in airs.values():
    o_air.write(json.dumps({"type": "Feature",
                            "properties": {"n": name, "k": kind, "iata": iata},
                            "geometry": g}, ensure_ascii=False) + "\n")
    o_airp.write(json.dumps({"type": "Feature",
                             "properties": {"n": name, "k": kind, "iata": iata},
                             "geometry": {"type": "Point",
                                          "coordinates": [round(pt[0], 5), round(pt[1], 5)]}},
                            ensure_ascii=False) + "\n")
    cnt["air_" + kind] += 1
for name, k, pt in ports.values():
    o_port.write(json.dumps({"type": "Feature", "properties": {"n": name, "k": k},
                             "geometry": {"type": "Point",
                                          "coordinates": [round(pt[0], 5), round(pt[1], 5)]}},
                            ensure_ascii=False) + "\n")
    cnt["port_" + k] += 1
for name, pt in bcs.values():
    o_bc.write(json.dumps({"type": "Feature", "properties": {"n": name},
                           "geometry": {"type": "Point",
                                        "coordinates": [round(pt[0], 5), round(pt[1], 5)]}},
                          ensure_ascii=False) + "\n")
    cnt["bc"] += 1

for f in (o_rail, o_air, o_airp, o_fer, o_port, o_bc):
    f.close()
print("\n统计：")
for k in sorted(cnt):
    print("  %-12s %8d" % (k, cnt[k]))
