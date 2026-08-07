#!/usr/bin/env python3
"""Google Routes API (computeRoutes, TRANSIT) で駅→枢纽の真値所要時間を取る。

使い方:
  key を環境変数 GOOGLE_ROUTES_KEY か .routes_key ファイル（gitignore済）に置き、
  python3 fetch_truth.py --pilot   # 大阪市概略bbox + けいはんな線 ≈269駅×4 = 1076件
  python3 fetch_truth.py --all     # 全842駅×4 = 3368件

方針:
- 出発時刻は「次の水曜 10:30 JST」= 平日日中。モデル側の口径（日中ダイヤ）に合わせる
- レスポンスは生のまま truth_cache/ に1件ずつ保存（中断・再開可）。
  站到站時間への換算（徒歩レグ・初乗り待ちの控除）はモデル比較の段で行い、
  ここでは一切加工しない —— 生データさえあれば口径は後で何度でも切り直せる
- 1.0s/req に絞る（既定クォータ 3000QPM に対し十分保守的）
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "truth_cache")
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# 枢纽の代表座標（index.html の HUB_LL と同一）
HUBS = {
    "梅田": (34.7025, 135.4959),
    "難波": (34.6636, 135.5008),
    "天王寺": (34.6465, 135.5140),
    "京橋": (34.6968, 135.5340),
}

FIELDS = ("routes.duration,routes.distanceMeters,"
          "routes.legs.duration,routes.legs.steps.travelMode,"
          "routes.legs.steps.staticDuration,"
          "routes.legs.steps.transitDetails")

PILOT_BBOX = (34.58, 135.40, 34.77, 135.60)   # 大阪市の概略
PILOT_EXTRA = {"荒本", "吉田", "新石切", "額田", "石切",
               "学研北生駒", "学研奈良登美ヶ丘", "長田"}   # けいはんな線方面


def next_weekday_1030_jst():
    """次の水曜 10:30 JST を RFC3339 で返す（当日が水曜でも次週にする）"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    days = (2 - now.weekday()) % 7 or 7
    d = (now + datetime.timedelta(days=days)).replace(
        hour=10, minute=30, second=0, microsecond=0)
    return d.isoformat()


def get_key():
    k = os.environ.get("GOOGLE_ROUTES_KEY")
    if not k and os.path.exists(os.path.join(HERE, ".routes_key")):
        k = open(os.path.join(HERE, ".routes_key")).read().strip()
    if not k:
        sys.exit("key が無い: 環境変数 GOOGLE_ROUTES_KEY か .routes_key に置く")
    return k


def query(key, olat, olon, dlat, dlon, depart):
    body = json.dumps({
        "origin": {"location": {"latLng": {"latitude": olat, "longitude": olon}}},
        "destination": {"location": {"latLng": {"latitude": dlat, "longitude": dlon}}},
        "travelMode": "TRANSIT",
        "departureTime": depart,
        "transitPreferences": {"allowedTravelModes": ["RAIL", "SUBWAY", "TRAIN", "LIGHT_RAIL"]},
        "computeAlternativeRoutes": False,
        "languageCode": "ja",
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": FIELDS,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="先頭N件だけ（試運転用）")
    args = ap.parse_args()
    if not (args.pilot or args.all):
        sys.exit("--pilot か --all を指定")

    key = get_key()
    depart = next_weekday_1030_jst()
    stations = json.load(open(os.path.join(HERE, "reach.json")))["stations"]
    if args.pilot:
        b = PILOT_BBOX
        stations = [s for s in stations
                    if (b[0] <= s["lat"] <= b[2] and b[1] <= s["lon"] <= b[3])
                    or s["name"] in PILOT_EXTRA]
    os.makedirs(CACHE, exist_ok=True)

    jobs = [(s, h) for s in stations for h in HUBS]
    todo = [(s, h) for s, h in jobs
            if not os.path.exists(os.path.join(CACHE, f'{s["station_id"]}_{h}.json'))]
    print(f"対象 {len(stations)}駅 × 4枢纽 = {len(jobs)}件, 残り {len(todo)}件, "
          f"出発時刻 {depart}", flush=True)
    if args.limit:
        todo = todo[:args.limit]

    fails = []
    for i, (s, h) in enumerate(todo):
        path = os.path.join(CACHE, f'{s["station_id"]}_{h}.json')
        t0 = time.time()
        try:
            r = query(key, s["lat"], s["lon"], *HUBS[h], depart)
            json.dump({"station_id": s["station_id"], "name": s["name"],
                       "hub": h, "depart": depart, "resp": r},
                      open(path, "w"), ensure_ascii=False, separators=(",", ":"))
        except Exception as e:
            code = getattr(e, "code", None)
            detail = ""
            if hasattr(e, "read"):
                try:
                    detail = e.read().decode()[:300]
                except Exception:
                    pass
            print(f'  {s["station_id"]} {s["name"]}→{h} 失敗: {code} {detail}', flush=True)
            fails.append((s["station_id"], h))
            if code in (401, 403):
                sys.exit("認証/権限エラー: key と Routes API の有効化を確認")
        time.sleep(max(0, 1.0 - (time.time() - t0)))
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(todo)}", flush=True)
    print(f"完了。失敗 {len(fails)} 件: {fails[:10]}", flush=True)


if __name__ == "__main__":
    main()
