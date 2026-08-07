#!/usr/bin/env python3
"""842站の徒歩等時圏（5/10/15/20分）を FOSSGIS 公共 Valhalla から取得する。

- 歩速は表示層と同じ 4.8km/h に合わせる（Valhalla 既定は 5.1）
- 公共サーバーなので 1.2s/req に絞り、429/5xx は指数バックオフで再試行
- 1駅ずつ cache/ に保存 → 中断しても再開できる
- 最後に walk_polys.json へまとめる（座標は1e-5度≈1mに丸め）
"""
import json, os, sys, time, urllib.request, urllib.error

URL = 'https://valhalla1.openstreetmap.de/isochrone'
CACHE = 'walk_cache'
OUT = 'walk_polys.json'
CONTOURS = [5, 10, 15, 20]
INTERVAL = 1.2

def fetch_one(lat, lon):
    body = json.dumps({
        'locations': [{'lat': lat, 'lon': lon}],
        'costing': 'pedestrian',
        'costing_options': {'pedestrian': {'walking_speed': 4.8}},
        'contours': [{'time': t} for t in CONTOURS],
        'polygons': True,
        'generalize': 25,
        'denoise': 0.2,
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'osaka-transit-map (personal project; polite 1req/1.2s)',
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)

def rings_by_contour(geo):
    """contour分ごとの ring 列（[外周, 穴...]、各 ring は [[lat,lon],...]）を返す"""
    out = {}
    for f in geo.get('features', []):
        c = f['properties'].get('contour')
        g = f['geometry']
        polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        rings = []
        for poly in polys:
            for ring in poly:
                rings.append([[round(p[1], 5), round(p[0], 5)] for p in ring])
        out[int(c)] = rings
    return out

def main():
    os.makedirs(CACHE, exist_ok=True)
    stations = json.load(open('reach.json'))['stations']
    todo = [s for s in stations
            if not os.path.exists(os.path.join(CACHE, s['station_id'] + '.json'))]
    print(f'{len(stations)}駅中 {len(todo)}駅を取得', flush=True)
    fails = []
    for i, s in enumerate(todo):
        path = os.path.join(CACHE, s['station_id'] + '.json')
        delay = INTERVAL
        for attempt in range(5):
            t0 = time.time()
            try:
                geo = fetch_one(s['lat'], s['lon'])
                rings = rings_by_contour(geo)
                if set(rings) != set(CONTOURS):
                    raise ValueError(f'contour欠落: {sorted(rings)}')
                json.dump(rings, open(path, 'w'), separators=(',', ':'))
                break
            except Exception as e:
                code = getattr(e, 'code', None)
                print(f'  {s["station_id"]} {s["name"]} 失敗({attempt+1}): {code or e}',
                      flush=True)
                if attempt == 4:
                    fails.append(s['station_id'])
                delay = min(60, delay * 2)
            finally:
                time.sleep(max(0, INTERVAL - (time.time() - t0)) if delay == INTERVAL
                           else delay)
        if (i + 1) % 50 == 0:
            print(f'  {i+1}/{len(todo)} 完了', flush=True)

    # まとめ
    merged = {}
    for s in stations:
        path = os.path.join(CACHE, s['station_id'] + '.json')
        if os.path.exists(path):
            merged[s['station_id']] = json.load(open(path))
    json.dump(merged, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
    size = os.path.getsize(OUT)
    print(f'完了: {len(merged)}/{len(stations)}駅, {OUT} = {size/1e6:.1f}MB, '
          f'失敗 {len(fails)}: {fails[:20]}', flush=True)

if __name__ == '__main__':
    main()
