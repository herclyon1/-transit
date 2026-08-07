"""阶段1: 服务型拓扑 + 所要時間モデル → 四枢纽への到達時間 reach.json

グラフ:
  節点 = (物理駅, 路線)  ... HANDOFF の「換乗大站每线一节点」
  乗車辺 = 服务型上の隣接停車駅。優等は跳站辺（各停辺の和ではない）
  乗換辺 = 同一複合体内の別路線ノード間。罰時は interchange_groups の段階式
  B層辺 = 乗車時間 + 期待待ち時間(60/headway/2)

2回解く:
  図A = A層のみ           -> t_default[4]
  図B = A層 + B層         -> t_low[4]
B は A の辺集合の上位集合なので必ず t_low <= t_default。これは断言して検証する。
"""
import heapq
import json
import os
import unicodedata
from collections import defaultdict

import interchange_groups as IG
from line_times import solve_speeds, segment_minutes, measured_segments

HERE = os.path.dirname(os.path.abspath(__file__))


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").strip()
    for suf in ("駅", "停留場", "停留所"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.replace(" ", "").replace("　", "")


def load():
    with open(os.path.join(HERE, "routes_osaka.json")) as f:
        return json.load(f)


MEASURED = measured_segments()

# 直通運転: OSM relation が事業者・路線境界で切れているせいで生じる偽の乗換。
# 日中も高頻度で直通する組だけを列挙する（朝夕のみの日生エクスプレス等は入れない）。
# 御堂筋線⇄北大阪急行は OSM 側で既に1本の pattern なのでここには不要。
# 阪神なんば線⇄近鉄奈良線の大阪難波は難波枢纽群内なので枢纽時間には影響しない。
THROUGH = {
    ("大阪市高速電気軌道|中央線", "近畿日本鉄道|けいはんな線"),   # 長田: 全列車直通
    ("大阪市高速電気軌道|堺筋線", "阪急電鉄|千里線"),             # 天神橋筋六丁目
    ("南海電気鉄道|高野線", "南海電気鉄道|泉北線"),               # 中百舌鳥: 準急/区急直通
}


def is_through(k1, k2):
    a, b = k1.split("#")[0], k2.split("#")[0]
    return (a, b) in THROUGH or (b, a) in THROUGH


def osaka_polygons():
    """japan.geojson から大阪府の多角形群（[[ [lon,lat],... ], ...]）を取り出す"""
    g = json.load(open(os.path.join(HERE, "japan.geojson")))
    for f in g["features"]:
        if f["properties"].get("nam_ja") == "大阪府":
            geom = f["geometry"]
            polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            return [ring for poly in polys for ring in poly]
    raise RuntimeError("大阪府 not in japan.geojson")


def pip(rings, lat, lon):
    """even-odd の点包含。穴も外周も同列に数える"""
    inside = False
    for r in rings:
        for i in range(len(r)):
            x1, y1 = r[i - 1]
            x2, y2 = r[i]
            if (y1 > lat) != (y2 > lat) and lon < (x1 - x2) * (lat - y2) / (y1 - y2) + x2:
                inside = not inside
    return inside


def build_graph(data, speeds, include_b):
    """(隣接リスト, 節点->駅, 駅->節点集合) を返す。節点は (station_id, line_key)。"""
    reg = {s["osm_id"]: s for s in data["stations"]}
    adj = defaultdict(list)
    edge_prov = {}
    board_wait = {}
    b_info = {}   # 低頻度ノードの路線キー -> (表示名, 特急券が要るか)
    node_station = {}
    station_nodes = defaultdict(set)

    for p in data["patterns"]:
        if p["layer"] == "excluded":
            continue
        if p["layer"] == "B" and not include_b:
            continue
        v, vprov, _ = speeds[(p["line_key"], p["service_class"])]
        # 期待待ち時間は「乗るとき1回」であって区間ごとではない。
        # 各辺に足すと3駅乗るのに3回待つ計算になり、低頻度層が永久に選ばれなくなる
        # （実測: 全駅で t_low == t_default になり ⚡ が一度も出なかった）。
        # そこで B層は別ノード空間に置き、待ち時間は乗換辺（＝乗車開始）に課す。
        lkey = p["line_key"] + ("#B" if p["layer"] == "B" else "")
        if p["layer"] == "B":
            if p.get("headway_daytime"):
                board_wait[lkey] = max(board_wait.get(lkey, 0.0),
                                       60.0 / p["headway_daytime"] / 2.0)
            disp = p["line_key"].split("|", 1)[-1]
            if p["service_class"] not in ("普通",):
                disp = f'{disp} {p["service_class"]}'
            prev = b_info.get(lkey)
            b_info[lkey] = (disp, bool(p.get("fare_extra")) or (prev[1] if prev else False))
        sids = [reg[i]["station_id"] for i in p["stops"] if i in reg]
        if len(sids) != len(p["stops"]):
            continue
        names = p["stop_names"]
        for sid in sids:
            n = (sid, lkey)
            node_station[n] = sid
            station_nodes[sid].add(n)
        for idx, (a, b, km) in enumerate(zip(sids, sids[1:], p["seg_km"])):
            if a == b:
                continue
            # 公式時刻表の実測があればモデルより優先する
            key = (p["line_key"], names[idx], names[idx + 1])
            t = MEASURED.get(key)
            eprov = PROV_RANK["measured"] if t is not None else PROV_RANK[vprov]
            if t is None:
                t = segment_minutes(km, v)
            na, nb = (a, lkey), (b, lkey)
            adj[na].append((nb, t))
            adj[nb].append((na, t))
            edge_prov[(na, nb)] = edge_prov[(nb, na)] = eprov

    # 乗換辺: 同一物理駅の別路線ノード間 + 同一複合体の別駅間
    sid_name = {}
    sid_op = defaultdict(set)
    for s in reg.values():
        if "station_id" in s:
            sid_name[s["station_id"]] = norm(s["name"])
    for p in data["patterns"]:
        for i in p["stops"]:
            if i in reg and "station_id" in reg[i]:
                sid_op[reg[i]["station_id"]].add(p["operator"])

    complex_members = defaultdict(set)
    for sid, nm in sid_name.items():
        g = IG.group_of(nm)
        if g:
            complex_members[g].add(sid)

    def link(n1, n2, minutes):
        # 乗車開始にあたるので、低頻度層のノードへ入る向きにだけ期待待ち時間を課す
        adj[n1].append((n2, minutes + board_wait.get(n2[1], 0.0)))
        adj[n2].append((n1, minutes + board_wait.get(n1[1], 0.0)))

    for sid, nodes in station_nodes.items():
        nodes = list(nodes)
        g = IG.group_of(sid_name.get(sid, ""))
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                op_a = nodes[i][1].split("|")[0]
                op_b = nodes[j][1].split("|")[0]
                if is_through(nodes[i][1], nodes[j][1]):
                    # 直通運転: 乗ったまま走り抜けるので罰時なし
                    link(nodes[i], nodes[j], 0.0)
                else:
                    link(nodes[i], nodes[j], IG.transfer_minutes(g, op_a, op_b))

    for g, sids in complex_members.items():
        sids = [s for s in sids if s in station_nodes]
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                if sids[i] == sids[j]:
                    continue
                for n1 in station_nodes[sids[i]]:
                    for n2 in station_nodes[sids[j]]:
                        link(n1, n2, IG.transfer_minutes(g, "x", "y"))

    return adj, node_station, station_nodes, sid_name, complex_members, edge_prov, b_info


PROV_RANK = {"measured": 0, "anchored": 1, "borrowed": 2}
PROV_NAME = ["measured", "anchored", "borrowed"]


def dijkstra_multi(adj, sources, edge_prov=None, b_info=None):
    """最短時間と、その経路上で最も弱い出典等級を返す。

    prov は経路上の最悪値を採る —— 1区間でも borrowed が混ざれば、
    その駅の数値は borrowed 相当の不確かさを持つ。
    """
    dist, prov, via = {}, {}, {}
    pq = []
    for s in sources:
        dist[s] = 0.0
        prov[s] = 0
        via[s] = None
        heapq.heappush(pq, (0.0, s))
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist.get(v, 1e18) - 1e-9:
                dist[v] = nd
                r = edge_prov.get((u, v), 0) if edge_prov else 0
                prov[v] = max(prov[u], r)
                # 経路上で最初に乗った低頻度系統を覚えておく（popup の ⚡ 表示用）
                via[v] = via[u] or ((b_info or {}).get(v[1]))
                heapq.heappush(pq, (nd, v))
    return dist, prov, via


def hub_times(data, speeds, include_b):
    adj, node_station, station_nodes, sid_name, complex_members, edge_prov, b_info = build_graph(
        data, speeds, include_b)
    out, out_prov, out_via = {}, {}, {}
    for hub in IG.HUBS:
        srcs = [n for sid in complex_members.get(hub, ()) for n in station_nodes.get(sid, ())]
        if not srcs:
            print(f"  ★枢纽 {hub} の節点が見つからない")
            out[hub] = {}
            out_prov[hub] = {}
            out_via[hub] = {}
            continue
        dist, prov, via = dijkstra_multi(adj, srcs, edge_prov, b_info)
        best, bp, bv = {}, {}, {}
        for n, d in dist.items():
            sid = node_station[n]
            if d < best.get(sid, 1e18):
                best[sid] = d
                bp[sid] = prov[n]
                bv[sid] = via[n]
        out[hub] = best
        out_prov[hub] = bp
        out_via[hub] = bv
    return out, station_nodes, sid_name, out_prov, out_via


# 枢纽は駅群なので、枢纽間の所要時間は「群内のどの駅どうしでもよい最短」になる。
# 御堂筋線での所要時間より短く出るのは正常:
#   梅田→難波 は 四つ橋線 西梅田→なんば(6分) が最短で、御堂筋線の9分ではない
#   難波→天王寺 は 大和路線 JR難波→新今宮→天王寺(5分) が最短
# したがって期待幅は「群意味論での最短」に合わせる。
RULER = [
    ("梅田", "難波", 5, 10),
    ("梅田", "天王寺", 12, 18),
    ("梅田", "京橋", 5, 8),
    ("難波", "天王寺", 4, 8),
    ("梅田", "新大阪", 3, 6),
    ("難波", "京橋", 10, 16),
]
# 公式PDFと直接突き合わせる路線内チェック（群意味論の影響を受けない）
LINE_RULER = [
    ("大阪市高速電気軌道|御堂筋線", "梅田", "なんば", 9.0),
    ("大阪市高速電気軌道|御堂筋線", "梅田", "天王寺", 15.0),
    ("大阪市高速電気軌道|御堂筋線", "なんば", "天王寺", 6.0),
]


def main():
    data = load()
    print("巡航速度の解決:")
    speeds = solve_speeds(data["patterns"])
    prov = defaultdict(int)
    for v, p, _ in speeds.values():
        prov[p] += 1
    print("  provenance:", dict(prov))

    print("\n図A(既定) / 図B(低頻度優等を含む) を解く...")
    ta, station_nodes, sid_name, pa, _ = hub_times(data, speeds, include_b=False)
    tb, _, _, _, vb = hub_times(data, speeds, include_b=True)

    # 標尺チェック
    name_sid = defaultdict(list)
    for sid, nm in sid_name.items():
        name_sid[nm].append(sid)
    print("\n[標尺] 枢纽間の所要時間（既定ビュー）")
    ok = True
    for a, b, lo, hi in RULER:
        cands = [s for s in name_sid.get(norm(b), []) if s in ta.get(a, {})]
        g = IG.group_of(norm(b))
        if g:
            cands = [s for s in sid_name if IG.group_of(sid_name[s]) == g and s in ta.get(a, {})]
        if not cands:
            print(f"  {a}→{b}: 到達不能 ★")
            ok = False
            continue
        t = min(ta[a][s] for s in cands)
        mark = "OK" if lo <= t <= hi else "★外れ"
        if not (lo <= t <= hi):
            ok = False
        print(f"  {a}→{b}: {t:5.1f}分 (期待 {lo}-{hi}分) {mark}")

    # 単調性の断言
    bad = 0
    for hub in IG.HUBS:
        for sid, d in ta[hub].items():
            if tb[hub].get(sid, 1e18) > d + 1e-6:
                bad += 1
    print(f"\n[断言] t_low <= t_default 違反: {bad} 件 {'OK' if bad == 0 else '★'}")

    v0 = json.load(open(os.path.join(HERE, "stations_final.json")))
    reg = {s["osm_id"]: s for s in data["stations"]}
    # 同じ物理駅に複数ノードがあるので、v0の513站に一致したノードを優先して代表にする
    sid_pos = {}
    for s in sorted(reg.values(), key=lambda x: 0 if x.get("v0") else 1):
        if "station_id" in s and s["station_id"] not in sid_pos:
            sid_pos[s["station_id"]] = (s["station_lat"], s["station_lon"], s["name"],
                                        s.get("grp", ""))
    # 事業者は その駅に停まる服务型から集める（v0の513站に載らない緩衝帯の駅にも付く）
    sid_ops = defaultdict(set)
    for p_ in data["patterns"]:
        if p_["layer"] == "excluded":
            continue
        for i in p_["stops"]:
            if i in reg and "station_id" in reg[i]:
                sid_ops[reg[i]["station_id"]].add(p_["operator"])
    # 抽出bboxの外（東海道本線が関東まで伸びている等）は地図の対象外
    BB = (34.27, 135.09, 35.06, 135.78)
    # 「府内かどうか」は v0 リスト所属ではなく府境界の点包含で決める。
    # v0 は阪堺の停留場を取り零しているので、in_v0 を府内フラグに流用すると
    # 天王寺駅前が「府外」表示になる誤標になっていた。
    opolys = osaka_polygons()
    rows = []
    flips = 0
    for sid, (lat, lon, nm, grp) in sorted(sid_pos.items()):
        if not (BB[0] <= lat <= BB[2] and BB[1] <= lon <= BB[3]):
            continue
        td = [ta[h].get(sid) for h in IG.HUBS]
        tl = [tb[h].get(sid) for h in IG.HUBS]
        if all(x is None for x in tl):
            continue
        if min([x for x in tl if x is not None]) > 120:
            continue
        in_osaka = pip(opolys, lat, lon)
        if in_osaka != bool(grp):
            flips += 1
        rows.append({
            "station_id": sid, "name": nm, "lat": lat, "lon": lon, "grp": grp,
            "in_osaka": in_osaka, "ops": sorted(sid_ops.get(sid, ())),
            "t_default": [None if x is None else round(x, 1) for x in td],
            "t_low": [None if x is None else round(x, 1) for x in tl],
            "prov": [PROV_NAME[pa[h][sid]] if sid in pa[h] else None for h in IG.HUBS],
            "via": [(vb[h].get(sid) or [None, False])[0] for h in IG.HUBS],
            "fare": [bool((vb[h].get(sid) or [None, False])[1]) for h in IG.HUBS],
        })
    path = os.path.join(HERE, "reach.json")
    with open(path, "w") as f:
        json.dump({"hubs": IG.HUBS, "stations": rows}, f, ensure_ascii=False)
    n_in = sum(1 for r in rows if r["in_osaka"])
    print(f"\n{len(rows)} 駅 (府内 {n_in} / 府外 {len(rows)-n_in}, "
          f"v0旗と食い違い {flips} 駅) -> {path}")
    return ok


if __name__ == "__main__":
    main()
