"""阶段1: 所要時間モデル。t_seg = 停車損失 + 駅間距離 / 巡航速度

停車損失は Osaka Metro 公式PDF（御堂筋線・谷町線・四つ橋線, 49区間）の実測から
プールで回帰して 1.00分。残差中央値 0.21分・最大 1.17分。
  回帰: t[分] = 1.005 + 0.939×d[km]  (n=49)
線ごとの二変数回帰は不能（1線の駅間距離が 1〜2.5km に固まっていて識別できず、
四つ橋線では切片が負になった）。よって停車損失を 1.00分 に固定し、
線×種別ごとに巡航速度だけをアンカーから逆算する。

巡航速度は物理量ではなく「実測所要時間を再現する当てはめ値」である。
純粋な走行性能から外挿してはいけない —— 阪急京都線の普通は最高115km/hの線を走るが
優等の待避で待たされるため実効62.6km/hしか出ない。だからアンカー無しの線は
同種別の中央値を借りる（prov=borrowed）ことにして、走行性能からの推定はしない。

prov:
  measured  公式時刻表から直接（Metro3線）
  anchored  当該線×種別の実測所要時間から巡航速度を逆算
  borrowed  同種別の他線から巡航速度を借用。誤差が大きい可能性あり
"""

STOP_LOSS_MIN = 1.00  # 停車1回あたりの損失（停車時分＋加減速ロス）

# 実測所要時間アンカー。minutes は日中の代表値。
ANCHORS = [
    # --- JR西日本
    {"line": "西日本旅客鉄道|大阪環状線", "cls": "普通", "a": "大阪", "b": "京橋", "min": 6.5,
     "src": "https://transit.yahoo.co.jp/timetable/25901/7201", "note": "検索実測 6-7分の中央"},
    {"line": "西日本旅客鉄道|大阪環状線", "cls": "普通", "a": "天王寺", "b": "京橋", "min": 14.5,
     "src": "https://transit.yahoo.co.jp/timetable/26062/7200", "note": "内回り 14-15分"},
    {"line": "西日本旅客鉄道|北陸本線・湖西線・東海道本線・山陽本線", "cls": "新快速",
     "a": "大阪", "b": "高槻", "min": 15,
     "src": "https://kansai-norikae.com/shinkaisoku/", "note": "大阪〜高槻 約15分"},
    {"line": "西日本旅客鉄道|阪和線", "cls": "快速", "a": "天王寺", "b": "鳳", "min": 14.5,
     "src": "https://transit.yahoo.co.jp/search/result/天王寺-鳳", "note": "関空/紀州路/区間快速 14-15分"},
    {"line": "西日本旅客鉄道|阪和線", "cls": "普通", "a": "天王寺", "b": "鳳", "min": 29.5,
     "src": "https://transit.yahoo.co.jp/search/result/天王寺-鳳", "note": "普通 28-31分"},
    # --- 阪急
    {"line": "阪急電鉄|京都本線", "cls": "普通", "a": "大阪梅田", "b": "高槻市", "min": 35,
     "src": "https://www.navitime.co.jp/diagram/depArrTimeList?departure=00007400&arrival=00002608&line=00000651&updown=0",
     "note": "普通 約35分。優等の待避で各停は大きく遅い"},
    {"line": "阪急電鉄|京都本線", "cls": "特急", "a": "大阪梅田", "b": "高槻市", "min": 23,
     "src": "https://www.navitime.co.jp/diagram/depArrTimeList?departure=00007400&arrival=00002608&line=00000651&updown=0",
     "note": "特急 約23分"},
    # --- 近鉄
    {"line": "近畿日本鉄道|快速急行", "cls": "快速急行", "a": "大阪難波", "b": "近鉄奈良", "min": 37,
     "src": "https://kansai-norikae.com/kintetsunara-line/", "note": "快速急行 35〜40分の中央"},
    # --- 南海
    {"line": "南海電気鉄道|本線", "cls": "急行", "a": "堺", "b": "なんば", "min": 12,
     "src": "https://www.navitime.co.jp/diagram/depArrTimeList?departure=00002863&arrival=00007182&line=00000821&updown=0",
     "note": "急行/空港急行 11-13分"},
]

# 種別ごとの既定巡航速度(km/h)。アンカーが無い線に借用する。
# 値は build_reach.py の実行時にアンカーから中央値を計算して上書きされる。
# ここに書いてあるのは、その種別のアンカーが1本も無い場合の最終フォールバック。
CLASS_FALLBACK_V = {
    "普通": 63.1,      # Metro3線プール実測
    "準急": 70.0,
    "区間急行": 75.0,
    "急行": 80.0,
    "快速急行": 80.0,
    "快速": 85.0,
    "新快速": 100.0,
    "特急": 90.0,
    "ライナー": 90.0,
}
# 地下鉄・新交通・モノレール・軌道は Metro 実測をそのまま使う（駅間が短く性格が同じ）
METRO_V = 63.1
METRO_OPERATORS = {"大阪市高速電気軌道", "阪堺電気軌道", "大阪モノレール", "神戸新交通"}


def arc(pattern, a, b):
    """停車駅列の a〜b 区間の (距離km, 区間数)。環状線は短い側を採る。"""
    names = pattern["stop_names"]
    if a not in names or b not in names:
        return None
    i, j = names.index(a), names.index(b)
    lo, hi = min(i, j), max(i, j)
    fwd_km, fwd_n = sum(pattern["seg_km"][lo:hi]), hi - lo
    # 環状の場合、外側を回る経路も候補になる
    total_km, total_n = sum(pattern["seg_km"]), len(names) - 1
    back_km, back_n = total_km - fwd_km, total_n - fwd_n
    is_loop = names[0] == names[-1] or fwd_n > total_n / 2
    if is_loop and back_n > 0 and back_km < fwd_km:
        return back_km, back_n
    return fwd_km, fwd_n


def solve_speeds(patterns, log=print):
    """アンカーから 線×種別 の巡航速度を逆算し、無い組合せは同種別の中央値を借りる。

    戻り値: {(line_key, service_class): (v_kmh, prov, detail)}
    """
    by_key = {}
    for p in patterns:
        by_key.setdefault((p["line_key"], p["service_class"]), []).append(p)

    solved = {}
    for an in ANCHORS:
        key = (an["line"], an["cls"])
        best = None
        for p in by_key.get(key, []):
            r = arc(p, an["a"], an["b"])
            # 最短経路のパターンを採る。区間数が多いものは遠回りの系統
            if r and (best is None or r[1] < best[1]):
                best = r
        if best is None:
            log(f"  ★アンカー照合できず: {an['line']}|{an['cls']} {an['a']}→{an['b']}")
            continue
        km, nseg = best
        run = an["min"] - nseg * STOP_LOSS_MIN
        if run <= 0:
            log(f"  ★停車損失だけで実測を超過: {an['line']}|{an['cls']} {an['a']}→{an['b']}")
            continue
        v = km / run * 60
        solved[key] = (round(v, 1), "anchored",
                       f"{an['a']}→{an['b']} {km:.1f}km {nseg}区間 実測{an['min']}分 / {an['src']}")

    # 種別ごとの中央値を作る
    per_class = {}
    for (lk, cls), (v, _, _) in solved.items():
        per_class.setdefault(cls, []).append(v)
    class_v = {}
    for cls, vs in per_class.items():
        vs.sort()
        class_v[cls] = vs[len(vs) // 2]
    log(f"  アンカー由来の種別中央値: { {k: round(v,1) for k, v in class_v.items()} }")

    out = dict(solved)
    for key in by_key:
        if key in out:
            continue
        lk, cls = key
        op = lk.split("|")[0]
        if op in METRO_OPERATORS:
            out[key] = (METRO_V, "measured",
                        "Osaka Metro公式PDF 3線49区間のプール実測（駅間が短く性格が同じ軌道系）")
        elif cls in class_v:
            out[key] = (class_v[cls], "borrowed", f"同種別({cls})のアンカー中央値を借用")
        else:
            out[key] = (CLASS_FALLBACK_V.get(cls, 70.0), "borrowed",
                        f"種別({cls})のアンカーが無く既定値を使用")
    return out


def segment_minutes(km, v_kmh):
    return STOP_LOSS_MIN + km / v_kmh * 60


def measured_segments(path=None):
    """Osaka Metro 公式PDFの実測駅間時分を {(路線キー, 駅名A, 駅名B): 分} で返す。

    モデルで近似せず実測をそのまま使う。都心部の短い駅間はモデルが系統的に速すぎるため
    （梅田→なんば は実測9分に対しモデル7.3分）。3線ぶんだけだが枢纽3つがこの3線上にある。
    """
    import json
    import os
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "anchors_metro.json")
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path) as f:
        data = json.load(f)
    for line, o in data.items():
        lk = f"大阪市高速電気軌道|{line}"
        for s in o["segments"]:
            out[(lk, s["from"], s["to"])] = float(s["min"])
            out[(lk, s["to"], s["from"])] = float(s["min"])
    return out
