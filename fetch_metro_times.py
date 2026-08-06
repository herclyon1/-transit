"""阶段1: Osaka Metro 公式PDF時刻表から実測の駅間所要時分を取る。

時間層で唯一の一次資料。GTFS が無いので、公開されている PDF ダイヤから直接読む。
公式サイトで PDF が置かれているのは御堂筋線・谷町線・四つ橋線の3線のみ（2026-08 実測）。
他線・他社はこの3線で較正した所要時間モデル（line_times.py）で推定する。

駅間所要は「隣接駅の発時刻差の最頻値」で取る。時刻表は分単位なので最頻値＝実際の表定所要分。
駅対の直接差分は使えない: 運転間隔(4-5分)が駅間所要(2分)より長いため、
最小差分マッチが一本前の列車を拾ってしまう。
"""
import collections
import json
import os
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

BASE = "https://subway.osakametro.co.jp/guide/libray/20200411_12_omgenbin/"
# 公式サイトに PDF があるのはこの3線だけ。他は時刻表検索(JS)のみで静的PDFが無い
PDFS = {
    "御堂筋線": "R1_kudari_1.pdf",
    "谷町線": "R2_kudari_1.pdf",
    "四つ橋線": "R3_nobori_1.pdf",
}
DAYTIME = (10 * 60, 16 * 60)  # 日中(10-16時)発の列車だけ使う


def fetch(name, fn):
    path = os.path.join(RAW, f"metro_{name}.pdf")
    if not os.path.exists(path):
        r = requests.get(BASE + fn, timeout=120)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
    return path


def read_rows(path):
    """PDF → {駅名: [発時刻(分), ...]} と駅の並び。"""
    import pypdf
    rows, order = {}, []
    for page in pypdf.PdfReader(path).pages:
        for line in page.extract_text().split("\n"):
            m = re.match(r"^(\S+?)\s+((?:\d{1,2}:\d{2}\s*)+)$", line.strip())
            if not m:
                continue
            st = m.group(1)
            ts = [int(h) * 60 + int(mi)
                  for h, mi in re.findall(r"(\d{1,2}):(\d{2})", m.group(2))]
            if st not in rows:
                rows[st] = []
                order.append(st)
            rows[st] += ts
    return order, rows


def segment_minutes(order, rows):
    out = []
    for a, b in zip(order, order[1:]):
        dep = sorted(t for t in rows[a] if DAYTIME[0] <= t < DAYTIME[1])
        arr = sorted(rows[b])
        diffs = []
        for t in dep:
            cand = [u - t for u in arr if 0 < u - t <= 12]
            if cand:
                diffs.append(min(cand))
        if not diffs:
            out.append(None)
            continue
        (val, n), = collections.Counter(diffs).most_common(1)
        out.append({"from": a, "to": b, "min": val, "n": n, "samples": len(diffs)})
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    result = {}
    for name, fn in PDFS.items():
        order, rows = read_rows(fetch(name, fn))
        segs = [s for s in segment_minutes(order, rows) if s]
        result[name] = {"source": BASE + fn, "stations": order, "segments": segs}
        total = sum(s["min"] for s in segs)
        print(f"{name}: {len(order)}駅 {len(segs)}区間 端から端まで {total}分")
    path = os.path.join(HERE, "anchors_metro.json")
    with open(path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"-> {path}")


if __name__ == "__main__":
    main()
