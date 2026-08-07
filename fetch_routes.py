"""阶段0: 从 OSM 抓 route relation（含优等列车停站型）+ 成员站点 + 成员轨道几何。

GTFS-JP 无大阪轨道数据（2026-08 实测: gtfs-data.jp 全量 547 feed 中大阪府仅 1 条高速巴士），
所以拓扑走 OSM route relation。relation 自带快速/急行/特急的跳站型，这是 v1 建图的基础。

结果缓存到 raw/，已存在则跳过，方便断点续抓（Overpass 会限流）。
"""
import json, os, time
import requests

BBOX = "34.27,135.09,35.06,135.78"
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HEADERS = {"User-Agent": "osaka-station-map-demo/0.1 (personal research)"}

# 旅客用軌道の route relation。service 線・貨物は route=train でも別途除外する（タグで判別）
REL_SEL = f'rel["type"="route"]["route"~"^(train|subway|monorail|tram|light_rail)$"]({BBOX})'

QUERIES = {
    # relation 本体: タグ + メンバー(ref/role)。停車駅の順序はここに入る
    "relations": f"[out:json][timeout:300];\n{REL_SEL};\nout body;",
    # relation のメンバーノード = 停車駅ノード（名前・座標つき）
    "rel_nodes": f"[out:json][timeout:300];\n{REL_SEL}->.r;\nnode(r.r);\nout body;",
    # relation のメンバーway = 軌道幾何（駅間の沿線距離を出すため）
    "rel_ways": f"[out:json][timeout:600];\n{REL_SEL}->.r;\nway(r.r);\nout geom;",
    # 阪堺の停留所は railway=station ではなく tram_stop（v0 で取りこぼしたぶん）
    "tram_stops": f'[out:json][timeout:180];\nnode["railway"="tram_stop"]({BBOX});\nout body;',
    # route relation が存在しない旅客線の代替: 線名つき way の幾何 + 沿線の駅ノード。
    # 実測(2026-08): bbox 内の旅客線で relation 皆無なのは京阪本線・中之島線・鴨東線のみ。
    # 他の未カバー線名は貨物線(城東貨物/大阪ターミナル/関西本線貨物支線)・遊具(子供汽車/SLスチーム号)・
    # 府外(和田岬線)・空港内連絡(ウイングシャトル)なので旅客ネットワークからは除外する。
    "fallback_ways": (
        "[out:json][timeout:300];\n"
        'way["railway"~"^(rail|light_rail)$"]["name"~"京阪本線|中之島線|鴨東線"]'
        f"({BBOX});\nout geom;"
    ),
    "fallback_nodes": (
        "[out:json][timeout:300];\n"
        'way["railway"~"^(rail|light_rail)$"]["name"~"京阪本線|中之島線|鴨東線"]'
        f"({BBOX})->.w;\n"
        'node(around.w:120)["railway"~"^(station|halt)$"];\nout body;'
    ),
}

# relation が無く、幾何+射影で駅順を復元する線（上の fallback_ways と対応）
FALLBACK_LINES = ["京阪電気鉄道京阪本線", "京阪電気鉄道中之島線", "京阪電気鉄道鴨東線"]


def overpass(query, tries_per_mirror=3):
    """三ミラー巡回 + 指数バックオフ。fetch_stations.py の巡回パターンを踏襲。"""
    delay = 2
    last = None
    for attempt in range(tries_per_mirror):
        for url in MIRRORS:
            try:
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=900)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    return r.json()
                # Overpass は 200 でも HTML のエラーページを返すことがある
                snippet = r.text[:200].replace("\n", " ")
                last = f"{url} -> {r.status_code} {snippet}"
                print("  retry:", last)
            except Exception as e:
                last = f"{url} -> {e}"
                print("  retry:", last)
            time.sleep(delay)
            delay = min(delay * 2, 64)
    raise RuntimeError(f"overpass failed after {tries_per_mirror} rounds: {last}")


def main():
    os.makedirs(RAW, exist_ok=True)
    for name, q in QUERIES.items():
        path = os.path.join(RAW, f"{name}.json")
        if os.path.exists(path):
            n = len(json.load(open(path)).get("elements", []))
            print(f"{name}: cached ({n} elements)")
            continue
        print(f"{name}: fetching...")
        data = overpass(q)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"{name}: {len(data.get('elements', []))} elements -> {path}")


if __name__ == "__main__":
    main()
