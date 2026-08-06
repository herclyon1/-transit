"""阶段0: OSM relation + 幾何fallback → 服务型拓扑 routes_osaka.json

出力する「服务型(service pattern)」= 1本の運行系統の停車駅列。
優等列車は各停の部分列ではなく独立した跳站列として保持する（v1 の時間層はこれを前提に辺を張る）。

駅間距離 seg_km は relation のメンバーway幾何を繋いだ沿線ポリラインへの射影で出す（直線距離ではない）。
"""
import json, math, os, re, sys, unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

# 大阪府 + 直近の府外緩衝帯。府界で線が切れると経路が壊れるため緩衝帯の駅も節点に残す。
OSAKA_BBOX = (34.27, 135.09, 35.06, 135.78)


def load(name):
    with open(os.path.join(RAW, f"{name}.json")) as f:
        return json.load(f)["elements"]


# ---------------------------------------------------------------- 幾何ユーティリティ

def meters(lat1, lon1, lat2, lon2):
    """局所平面近似。大阪スケール(~80km)では誤差無視できる。"""
    mlat = math.radians((lat1 + lat2) / 2)
    return math.hypot((lat2 - lat1) * 111320, (lon2 - lon1) * 111320 * math.cos(mlat))


def stitch(ways):
    """メンバーway列を端点マッチで1本のポリラインに繋ぐ。

    OSM の route relation はway順が概ね正しいが向きは揃っていないので、
    直前の終点に近い方の端点を始点として採用する。繋がらない箇所は切れ目として別セグメントにする。
    戻り値: [[(lat,lon), ...], ...]（切れ目ごとのポリライン）
    """
    segs = []
    cur = []
    for geom in ways:
        pts = [(p["lat"], p["lon"]) for p in geom]
        if len(pts) < 2:
            continue
        if not cur:
            cur = pts
            continue
        tail = cur[-1]
        d_head = meters(*tail, *pts[0])
        d_tail = meters(*tail, *pts[-1])
        if d_tail < d_head:
            pts = pts[::-1]
            d_head = d_tail
        if d_head > 60:  # 繋がっていない → 切れ目
            segs.append(cur)
            cur = pts
        else:
            cur.extend(pts[1:])
    if cur:
        segs.append(cur)
    return segs


def cumulative(poly):
    acc = [0.0]
    for a, b in zip(poly, poly[1:]):
        acc.append(acc[-1] + meters(*a, *b))
    return acc


def project(poly, acc, lat, lon):
    """点を折れ線に射影して (沿線距離m, 離隔m) を返す。"""
    best = None
    for i, (a, b) in enumerate(zip(poly, poly[1:])):
        ax, ay = a[1], a[0]
        bx, by = b[1], b[0]
        px, py = lon, lat
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        qx, qy = ax + t * dx, ay + t * dy
        off = meters(lat, lon, qy, qx)
        if best is None or off < best[1]:
            best = (acc[i] + meters(a[0], a[1], qy, qx), off)
    return best


def along_km(polys, stops):
    """停車駅列 → 駅間距離km列。複数セグメントに割れている場合は駅ごとに最良のセグメントを選ぶ。"""
    prepared = [(p, cumulative(p)) for p in polys if len(p) >= 2]
    if not prepared:
        return None
    placed = []
    for s in stops:
        cands = []
        for si, (poly, acc) in enumerate(prepared):
            d, off = project(poly, acc, s["lat"], s["lon"])
            cands.append((off, si, d))
        cands.sort()
        placed.append(cands[0])  # (離隔, セグ番号, 沿線位置)
    out = []
    for (o1, s1, d1), (o2, s2, d2), a, b in zip(placed, placed[1:], stops, stops[1:]):
        gc = meters(a["lat"], a["lon"], b["lat"], b["lon"])
        if s1 == s2 and o1 < 250 and o2 < 250:
            km = abs(d2 - d1) / 1000.0
            # 射影が破綻すると直線距離を下回る。その場合は直線×迂回係数に落とす
            if km * 1000 < gc * 0.98:
                km = gc * 1.08 / 1000.0
        else:
            km = gc * 1.08 / 1000.0
        out.append(round(km, 4))
    return out


# ---------------------------------------------------------------- 名前の正規化

_SUFFIX = re.compile(r"(駅|停留場|停留所)$")

# stations_final.json(漢字表記) と OSM(かな表記) の食い違い。実測で判明したぶんだけ。
NAME_ALIAS = {"難波": "なんば", "我孫子": "あびこ"}


def norm_name(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).strip()
    s = _SUFFIX.sub("", s)
    s = s.replace(" ", "").replace("　", "")
    return NAME_ALIAS.get(s, s)


# 列車愛称。種別の判定には使うが、路線キーからは落とさない
# （落とすと「特急ラピートα」が路線キー "α" に化ける）。
TRAIN_NAMES = {
    "特急": ["ラピート", "ひのとり", "アーバンライナー", "はるか", "くろしお", "サンダーバード",
            "こうのとり", "はまかぜ", "びわこエクスプレス", "しまかぜ", "あをによし",
            "青の交響曲", "まほろば", "らくラク", "サザン", "こうや", "りんかん", "泉北ライナー"],
    "新幹線": ["のぞみ", "ひかり", "こだま", "みずほ", "さくら", "つばめ"],
}
# 一般的な種別語。長いものから順に当てる（区間急行 が 急行 に食われないように）。路線キーからは落とす。
CLASS_TOKENS = [
    ("新快速", ["新快速"]),
    ("特急", ["快速特急", "通勤特急", "準特急", "特急"]),
    ("ライナー", ["ライナー"]),
    ("快速急行", ["快速急行"]),
    ("区間急行", ["区間急行", "区急"]),
    ("急行", ["空港急行", "急行"]),
    ("区間準急", ["区間準急"]),
    ("準急", ["準急行", "準急"]),
    ("快速", ["直通快速", "区間快速", "快速"]),
    ("普通", ["普通", "各駅停車", "各停"]),
]
ALL_STOP_ROUTES = {"subway", "monorail", "tram", "light_rail"}


def service_class(name, route):
    """(種別, 判定根拠, 推定フラグ) を返す。新幹線は専用種別にして後段で除外する。"""
    n = unicodedata.normalize("NFKC", name or "")
    for k in TRAIN_NAMES["新幹線"]:
        if k in n:
            return "新幹線", k, False
    for cls, keys in CLASS_TOKENS:
        for k in keys:
            if k in n:
                return cls, k, False
    for k in TRAIN_NAMES["特急"]:
        if k in n:
            return "特急", k, False
    if route in ALL_STOP_ROUTES:
        return "普通", None, True
    return "普通", None, True  # 種別語なしの train は各停系統とみなす（inferred を立てる）


_PAREN = re.compile(r"[（(\[].*?[）)\]]")
# 路線名に埋まっている社名。長いものから消す
_COMPANY_IN_NAME = ["大阪市高速電気軌道", "近畿日本鉄道", "南海電気鉄道", "京阪電気鉄道",
                    "阪神電気鉄道", "阪堺電気軌道", "泉北高速鉄道", "山陽電気鉄道",
                    "神戸電鉄", "能勢電鉄", "水間鉄道", "叡山電鉄", "京福電気鉄道",
                    "阪急電鉄", "大阪モノレール", "Osaka Metro", "Osaka Metor",
                    "JR", "ＪＲ", "近鉄", "阪急", "阪神", "南海", "京阪"]
# 「A => B」「: A -> B」等、括弧に入っていない方向表記
_DIRECTION = re.compile(r"\s*[:：]?\s*[^\s:：]+\s*(=>|->|⇒|→)\s*[^\s:：]+\s*$")
_OP_CANON = {"JR West": "西日本旅客鉄道", "JR西日本": "西日本旅客鉄道",
             "南海電鉄": "南海電気鉄道", "Kintetsu Corporation": "近畿日本鉄道",
             "阪神電車": "阪神電気鉄道", "阪堺電車": "阪堺電気軌道",
             "東海旅客鉄道株式会社": "東海旅客鉄道", "京福電気鉄道株式会社": "京福電気鉄道",
             "叡山電鉄株式会社": "叡山電鉄"}
# operator タグが空の relation 用。路線名から事業者を引く
_OP_FROM_NAME = [("南海", "南海電気鉄道"), ("阪急", "阪急電鉄"), ("阪神", "阪神電気鉄道"),
                 ("近鉄", "近畿日本鉄道"), ("京阪", "京阪電気鉄道"), ("阪堺", "阪堺電気軌道"),
                 ("能勢電鉄", "能勢電鉄"), ("水間", "水間鉄道"), ("泉北", "泉北高速鉄道"),
                 ("Osaka Metro", "大阪市高速電気軌道"), ("Osaka Metor", "大阪市高速電気軌道"),
                 ("JR", "西日本旅客鉄道"), ("ＪＲ", "西日本旅客鉄道")]
# 事業者をまたいで直通する運行系統は、直通先ではなく主たる運行会社に寄せる
_OP_BY_TRAIN = {"サザン": "南海電気鉄道", "ラピート": "南海電気鉄道",
                "泉北ライナー": "南海電気鉄道", "直通特急": "山陽電気鉄道",
                "関空快速": "西日本旅客鉄道", "紀州路快速": "西日本旅客鉄道",
                "大和路快速": "西日本旅客鉄道", "丹波路快速": "西日本旅客鉄道",
                "みやこ路快速": "西日本旅客鉄道", "直通快速": "西日本旅客鉄道",
                "区間快速": "西日本旅客鉄道", "はまかぜ": "西日本旅客鉄道",
                "こうのとり": "西日本旅客鉄道", "サンダーバード": "西日本旅客鉄道",
                "はるか": "西日本旅客鉄道", "くろしお": "西日本旅客鉄道"}


def canon_operator(operator, name=""):
    """路線名に社名が入っていればそれを優先する。

    operator タグは同じ路線でも relation ごとに揺れる（実測: 泉北線の上り/下りが
    南海電気鉄道 と 泉北高速鉄道 に割れていた）。路線名の方が識別子として安定している。
    """
    n = unicodedata.normalize("NFKC", name or "")
    for k, v in _OP_FROM_NAME:
        if k in n:
            return v
    op = unicodedata.normalize("NFKC", operator or "").split(";")[0].strip()
    op = _OP_CANON.get(op, op)
    if op:
        return op
    for k, v in _OP_BY_TRAIN.items():
        if k in n:
            return v
    return "(unknown)"


def line_key(name, operator):
    """節点分割用の路線キー。方向カッコ・社名・一般種別語を落として正規化する。

    列車愛称は落とさない（愛称列車は路線ではなく系統そのものが識別子になるため）。
    ここが揺れると同一路線が別ノードに割れて、存在しない乗換罰時が入る。
    """
    n = unicodedata.normalize("NFKC", name or "")
    n = _PAREN.sub("", n)
    n = _DIRECTION.sub("", n)
    # 愛称を退避してから種別語を落とす（「アーバンライナー」から ライナー が抜けるのを防ぐ）
    holds = {}
    for i, k in enumerate(sorted(sum(TRAIN_NAMES.values(), []), key=len, reverse=True)):
        if k in n:
            tok = f"\x00{i}\x00"
            holds[tok] = k
            n = n.replace(k, tok)
    for c in _COMPANY_IN_NAME:
        n = n.replace(c, "")
    for _, keys in CLASS_TOKENS:
        for k in keys:
            n = n.replace(k, "")
    for tok, k in holds.items():
        n = n.replace(tok, k)
    n = n.strip(" 　・:-ー―−")
    if not n:  # 種別語だけの名前だった
        n = _PAREN.sub("", unicodedata.normalize("NFKC", name or "")).strip()
    return f"{canon_operator(operator, name)}|{n}"


# ---------------------------------------------------------------- 駅レジストリ

def in_bbox(lat, lon):
    a, b, c, d = OSAKA_BBOX
    return a <= lat <= c and b <= lon <= d


def build_stations():
    """OSM の停車ノードを正準駅レジストリにする。物理的に別会社なら別ノードのままにする
    （HANDOFF の「換乗大站每线一节点」に対応。統合は interchange_groups が担当）。"""
    reg = {}
    for src in ("rel_nodes", "tram_stops", "fallback_nodes"):
        for n in load(src):
            t = n.get("tags", {})
            if not t.get("name"):
                continue
            reg[n["id"]] = {
                "osm_id": n["id"],
                "name": t["name"],
                "name_norm": norm_name(t["name"]),
                "lat": n["lat"],
                "lon": n["lon"],
                "railway": t.get("railway", ""),
                "operator": t.get("operator", ""),
                "ksj_line": t.get("KSJ2:LIN", ""),
            }
    return reg


def link_to_v0(reg, covered_ids):
    """stations_final.json(513站) と突き合わせて grp を付ける。

    同一駅に OSM ノードが複数あるため（KSJ2 一括取込のものと手書きのもの、方向別の stop ノード等）、
    服务型に実際に載っているノードを優先して選ぶ。優先しないと v0 の駅が
    「どの系統にも載らない孤立駅」に化ける（実測: 天満橋・淀屋橋・京橋 等 8 駅）。
    """
    v0 = json.load(open(os.path.join(HERE, "stations_final.json")))
    by_norm = defaultdict(list)
    for s in reg.values():
        by_norm[s["name_norm"]].append(s)
    matched, unmatched = 0, []
    for st in v0:
        cands = by_norm.get(norm_name(st["name"]), [])
        scored = []
        for c in cands:
            d = meters(st["lat"], st["lon"], c["lat"], c["lon"])
            if d < 900:
                # 服务型に載っているノードを優先し、その中で最寄りを採る
                scored.append((0 if c["osm_id"] in covered_ids else 1, d, c["osm_id"], c))
        if scored:
            scored.sort()
            c = scored[0][3]
            c["grp"] = st["grp"]
            c["v0"] = True
            matched += 1
        else:
            unmatched.append(st)
    return matched, unmatched


# ---------------------------------------------------------------- 服务型抽出

# 旅客軌道ネットワークから外れることが確認済みの v0 駅。理由は OSM の実データで裏を取ったもの。
EXPECTED_UNCOVERED = {
    "桜谷": "桜谷軽便鉄道(narrow_gauge/abandoned)の駅。公共交通ではない — OSM way 232286384/981962415 等で確認",
    "風の峠": "同上（桜谷軽便鉄道）",
    "高安山": "近鉄西信貴ケーブル(railway=funicular, OSM way 1372764165)。"
              "鋼索線は本抽出の railway 種別(rail/subway/monorail/tram/light_rail)に含めていない",
    "吹田貨物ターミナル": "貨物駅（旅客扱いなし）",
    "大阪貨物ターミナル": "貨物駅（旅客扱いなし）",
}

STOP_ROLES = {"stop", "stop_entry_only", "stop_exit_only", "station"}

# OSM の relation 自体が停車駅を取りこぼしている箇所の人工補丁。
# HANDOFF の三段 fallback（operatorタグ→KSJ2:LIN→人工補丁）の三段目にあたる。
# 実測: 阪堺線 relation に 今池停留場 が入っていない（新今宮駅前と今船の間）。
STOP_PATCHES = [
    {"match": "阪堺線", "insert": "今池", "after": "新今宮駅前", "before": "今船",
     "reason": "OSM relation に停留場が欠落。v0 の stations_final.json には存在する"},
]


def apply_stop_patches(rel_name, stops, reg):
    for p in STOP_PATCHES:
        if p["match"] not in rel_name:
            continue
        names = [s["name_norm"] for s in stops]
        want = norm_name(p["insert"])
        if want in names:
            continue
        a, b = norm_name(p["after"]), norm_name(p["before"])
        idx = None
        for i, (x, y) in enumerate(zip(names, names[1:])):
            if {x, y} == {a, b}:
                idx = i + 1
                break
        if idx is None:
            continue
        node = next((s for s in reg.values() if s["name_norm"] == want), None)
        if node:
            stops = stops[:idx] + [node] + stops[idx:]
    return stops


def relation_patterns(reg):
    rels = load("relations")
    ways = {w["id"]: w for w in load("rel_ways")}
    out = []
    for r in rels:
        t = r.get("tags", {})
        members = r.get("members", [])
        stop_refs = [m["ref"] for m in members if m["type"] == "node" and m["role"] in STOP_ROLES]
        if not stop_refs:
            stop_refs = [m["ref"] for m in members if m["type"] == "node" and not m["role"]]
        stops = [reg[i] for i in stop_refs if i in reg]
        # 連続重複を潰す。同一停留場に別ノードが二つ張られている例があるので名前でも見る
        # （実測: 阪堺線の 住吉・石津北 が連続二重に入る）。
        dedup = []
        for s in stops:
            if dedup and (dedup[-1]["osm_id"] == s["osm_id"]
                          or dedup[-1]["name_norm"] == s["name_norm"]):
                continue
            dedup.append(s)
        dedup = apply_stop_patches(t.get("name", ""), dedup, reg)
        if len(dedup) < 2:
            continue
        geoms = [ways[m["ref"]]["geometry"] for m in members
                 if m["type"] == "way" and not m["role"]
                 and m["ref"] in ways and ways[m["ref"]].get("geometry")]
        seg = along_km(stitch(geoms), dedup) if geoms else None
        if seg is None:
            seg = [round(meters(a["lat"], a["lon"], b["lat"], b["lon"]) * 1.08 / 1000, 4)
                   for a, b in zip(dedup, dedup[1:])]
        cls, kw, inferred = service_class(t.get("name", ""), t.get("route", ""))
        out.append({
            "src": f"osm:relation/{r['id']}",
            "operator": canon_operator(t.get("operator", ""), t.get("name", "")),
            "name": t.get("name", ""),
            "route": t.get("route", ""),
            "line_key": line_key(t.get("name", ""), t.get("operator", "")),
            "service_class": cls,
            "class_keyword": kw,
            "class_inferred": inferred,
            "stops": [s["osm_id"] for s in dedup],
            "stop_names": [s["name"] for s in dedup],
            "seg_km": seg,
        })
    return out


def _dijkstra(adj, src):
    import heapq
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, math.inf):
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


# OSM の幾何だけでは駅順が復元できない線の明示停車駅列。
# 中之島線(2008開業)は KSJ2(2007) に無く、地下線のため駅ノードが軌道から離れていて近接推定も効かない。
# 鴨東線は京都府内（府外緩衝帯）で bbox 端に掛かり幾何が切れる。
# いずれも駅数が少なく、順序は公開されている事実なので明示する方が幾何ヒューリスティックより確か。
FALLBACK_STOP_OVERRIDE = {
    "京阪電気鉄道中之島線": ["中之島", "渡辺橋", "大江橋", "なにわ橋", "天満橋"],
    "京阪電気鉄道鴨東線": ["三条", "神宮丸太町", "出町柳"],
}


def fallback_patterns(reg, covered_ids):
    """relation が無い旅客線を「線名way の軌道ネットワーク + 網距離順」で復元する。

    複線は平行way として別々に引かれているため、幾何を1本に繋ぐ(stitch)方式は破綻する。
    代わりに way のノード列からグラフを組み、最大連結成分の端点から Dijkstra を打って
    網距離で駅を並べる。駅間距離もこの網距離差から取る。
    """
    from fetch_routes import FALLBACK_LINES
    ways = load("fallback_ways")
    byline = defaultdict(list)
    for w in ways:
        nm = w.get("tags", {}).get("name")
        if nm in FALLBACK_LINES and w.get("geometry") and w.get("nodes"):
            byline[nm].append(w)
    out = []
    for nm, ws in byline.items():
        adj = defaultdict(list)
        coord = {}
        for w in ws:
            ids, geo = w["nodes"], w["geometry"]
            if len(ids) != len(geo):
                continue
            for nid, p in zip(ids, geo):
                coord[nid] = (p["lat"], p["lon"])
            for a, b in zip(zip(ids, geo), zip(ids[1:], geo[1:])):
                (ia, pa), (ib, pb) = a, b
                d = meters(pa["lat"], pa["lon"], pb["lat"], pb["lon"])
                adj[ia].append((ib, d))
                adj[ib].append((ia, d))
        if not coord:
            continue
        # 最大連結成分に絞る（孤立した側線・分断を落とす）
        seen, comps = set(), []
        for start in coord:
            if start in seen:
                continue
            stack, comp = [start], []
            seen.add(start)
            while stack:
                u = stack.pop()
                comp.append(u)
                for v, _ in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            comps.append(comp)
        comp = set(max(comps, key=len))

        # 駅をこの成分の最寄りノードにスナップ。
        # relation 側で既に拾われているノードは他社線の駅なので除く
        # （実測: JR東西線の大阪城北詰が京阪本線の軌道から60m以内に入り紛れ込んだ）。
        snapped = {}
        for s in reg.values():
            if s["osm_id"] in covered_ids:
                continue
            best = None
            for nid in comp:
                la, lo = coord[nid]
                if abs(la - s["lat"]) > 0.004 or abs(lo - s["lon"]) > 0.005:
                    continue
                d = meters(s["lat"], s["lon"], la, lo)
                if best is None or d < best[0]:
                    best = (d, nid)
            if best and best[0] < 130:
                prev = snapped.get(s["name_norm"])
                if prev is None or best[0] < prev[0]:
                    snapped[s["name_norm"]] = (best[0], best[1], s)
        if len(snapped) < 2:
            continue
        # 二重走査で線の両端(全ノード対象)を取り、その間の最短経路を「本線バックボーン」とする。
        # 網距離でそのまま並べると側線・支線スタブに吸われて順序が入れ替わる
        # （実測: 京阪本線で 天満橋 と 京橋 が逆転した）。バックボーンへの射影なら起きない。
        # 端点は駅ではなく全ノードから取る（駅で取ると終端駅の外側が主幹に入らず終端駅が落ちる）。
        d0, _ = _dijkstra(adj, next(iter(comp)))
        end_a = max((d, n) for n, d in d0.items())[1]
        da, prev = _dijkstra(adj, end_a)
        end_b = max((d, n) for n, d in da.items())[1]
        path, cur = [], end_b
        while cur is not None:
            path.append(cur)
            cur = prev.get(cur)
        backbone = [coord[n] for n in reversed(path)]
        if len(backbone) < 2:
            continue
        acc = cumulative(backbone)
        short = nm.replace("京阪電気鉄道", "")
        override = FALLBACK_STOP_OVERRIDE.get(nm)
        if override:
            # 明示停車駅列: 名前で引き、バックボーンに最も近いノードを採る
            seq = []
            for want in override:
                cands = [s for s in reg.values() if s["name_norm"] == norm_name(want)]
                best = None
                for s in cands:
                    d, off = project(backbone, acc, s["lat"], s["lon"])
                    if best is None or off < best[1]:
                        best = (d, off, s)
                if best:
                    seq.append(best)
        else:
            seq = []
            for _, _, st in snapped.values():
                # KSJ2:LIN(国土数値情報の線名)が付いていて別線を指すノードは他社線の駅。
                # 実測: JR東西線の大阪城北詰が京阪本線の軌道から60m以内に入り紛れ込んだ。
                ksj = st.get("ksj_line")
                if ksj and short not in ksj and ksj not in short:
                    continue
                d, off = project(backbone, acc, st["lat"], st["lon"])
                if off <= 60:  # バックボーン直上の駅だけ = この線の駅
                    seq.append((d, off, st))
            seq.sort(key=lambda x: x[0])
        if len(seq) < 2:
            continue
        stops = [s for _, _, s in seq]
        if override:
            # 明示列は幾何が怪しいので沿線距離を使わず直線×迂回係数にする（過小評価を避ける）
            seg = [round(meters(a["lat"], a["lon"], b["lat"], b["lon"]) * 1.08 / 1000, 4)
                   for a, b in zip(stops, stops[1:])]
        else:
            seg = [round(abs(b - a) / 1000, 4) for (a, _, _), (b, _, _) in zip(seq, seq[1:])]
        op = "京阪電気鉄道"
        out.append({
            "src": f"osm:ways-projection/{nm}",
            "operator": op,
            "name": f"{nm} 普通",
            "route": "train",
            "line_key": line_key(nm, op),
            "service_class": "普通",
            "class_keyword": None,
            "class_inferred": True,
            "stops": [s["osm_id"] for s in stops],
            "stop_names": [s["name"] for s in stops],
            "seg_km": seg,
        })
    return out


def dedupe(patterns):
    """同一系統の重複 relation（方向違い・分割違い）を潰す。停車駅集合が同じものは1本にする。"""
    best = {}
    for p in patterns:
        key = (p["line_key"], p["service_class"], tuple(sorted(p["stops"])))
        cur = best.get(key)
        if cur is None or len(p["stops"]) > len(cur["stops"]):
            best[key] = p
    return list(best.values())


def selfcheck(reg, pats, unmatched):
    """計画の検証項目1: 513站の被覆と孤立、線ごとの服务型数。

    stations_final.json の 513 件は物理駅数ではなく「同一駅の路線別ノード」を含む
    （本町×3、なんば×3、天王寺×3 等）。名前で突き合わせると潰れるので、
    被覆は距離ベースで測る: v0 の各点から 400m 以内に服务型の停車駅があるか。
    """
    covered_nodes = [reg[i] for p in pats for i in p["stops"] if i in reg]
    v0 = json.load(open(os.path.join(HERE, "stations_final.json")))
    iso = []
    for st in v0:
        near = any(abs(c["lat"] - st["lat"]) < 0.005 and abs(c["lon"] - st["lon"]) < 0.006
                   and meters(st["lat"], st["lon"], c["lat"], c["lon"]) < 400
                   for c in covered_nodes)
        if not near:
            iso.append(st)
    print("\n" + "=" * 60)
    print("[自检1] stations_final.json 513站 の被覆（400m以内に服务型の停車駅があるか）")
    print(f"  被覆 {len(v0) - len(iso)} / {len(v0)}   未被覆 {len(iso)}")
    surprise = []
    for st in iso:
        why = EXPECTED_UNCOVERED.get(st["name"])
        if why:
            print(f"    想定内 未被覆: {st['name']} ({st['grp']}) — {why}")
        else:
            surprise.append(st)
            print(f"    ★想定外 未被覆: {st['name']} ({st['grp']}) — 要調査")
    if not surprise:
        print("  → 未被覆はすべて理由が確認済み。旅客ネットワークとしての被覆は完全。")

    bykey = defaultdict(list)
    for p in pats:
        bykey[p["line_key"]].append(p)
    print(f"\n[自检2] 路線キー数: {len(bykey)}  服务型数: {len(pats)}")
    cls = defaultdict(int)
    for p in pats:
        cls[p["service_class"]] += 1
    print("  種別内訳:", dict(sorted(cls.items(), key=lambda x: -x[1])))
    inferred = sum(1 for p in pats if p["class_inferred"])
    print(f"  種別語なし(普通と推定): {inferred} / {len(pats)}")
    return iso


def main():
    reg = build_stations()
    print(f"駅レジストリ: {len(reg)} ノード")

    pats = relation_patterns(reg)
    print(f"relation 由来の服务型: {len(pats)}")
    covered_ids = {i for p in pats for i in p["stops"]}
    fb = fallback_patterns(reg, covered_ids)
    for p in fb:
        print(f"fallback: {p['name']} 駅数={len(p['stops'])}")
    pats = dedupe(pats + fb)
    print(f"重複除去後: {len(pats)}")

    covered_ids = {i for p in pats for i in p["stops"]}
    matched, unmatched = link_to_v0(reg, covered_ids)
    print(f"stations_final.json 513站 との突合: 一致 {matched} / 未一致 {len(unmatched)}")
    selfcheck(reg, pats, unmatched)

    stations = [s for s in reg.values() if any(s["osm_id"] in set(p["stops"]) for p in pats)] \
        if False else list(reg.values())
    out = {
        "stations": stations,
        "patterns": sorted(pats, key=lambda p: (p["line_key"], p["service_class"])),
    }
    path = os.path.join(HERE, "routes_osaka.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"\n-> {path}")


if __name__ == "__main__":
    main()
