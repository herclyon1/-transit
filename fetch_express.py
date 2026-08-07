"""阶段1補修: 優等列車の停車駅型を Wikipedia の駅一覧表から取る。

v1 の最大誤差源は「80線中48線が OSM に各停の停車駅型しか無い」こと。
京阪本線・南海高野線・近鉄各線・阪急宝塚本線・阪神本線 などの主力通勤線で
急行/特急の辺が張られず、沿線の所要時間が倍近く過大評価される
（実測: 枚方市→京橋 が 37.7分。実際の京阪特急は約20分）。

OSM に route relation が無いので Wikipedia の駅一覧表（●=停車 / ｜=通過）を使う。
wikitext 直読みは記事ごとに書式がばらつき破綻したので、レンダリング済みHTMLを
rowspan/colspan を展開してグリッド化してから読む。
"""
import html
import json
import os
import re
import time
from html.parser import HTMLParser

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://ja.wikipedia.org/w/api.php"
UA = {"User-Agent": "osaka-station-map-demo/0.1 (personal research)"}

# 記事名 -> (routes_osaka.json の line_key, 採らない種別)
# 通勤○○ は朝夕のみ、特急は既に OSM 側に愛称系統として入っているので落とす
PAGES = {
    "京阪本線": ("京阪電気鉄道|本線", {"通勤準急", "通勤快急", "ライナー", "快速特急洛楽"}),
    "南海高野線": ("南海電気鉄道|高野線", {"特急", "こうや", "りんかん", "泉北ライナー"}),
    "近鉄南大阪線": ("近畿日本鉄道|南大阪線", {"特急"}),
    "近鉄大阪線": ("近畿日本鉄道|大阪線", {"特急"}),
    "近鉄奈良線": ("近畿日本鉄道|奈良線", {"特急"}),
    "阪急宝塚本線": ("阪急電鉄|宝塚本線", {"通勤急行", "準急", "通勤特急"}),
    "阪神本線": ("阪神電気鉄道|本線", {"区間特急", "区間急行"}),
}
STOP = {"●", "◎", "○", "★"}
PASS = {"｜", "|", "↑", "↓", "‖", "▲", "△", "レ", "…", "-", "—", "－"}


class Grid(HTMLParser):
    """<table> を rowspan/colspan 展開してテキストの2次元配列にする。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.cur, self.row = [], None, None
        self.cell, self.depth = None, 0
        self.pending, self.ri = {}, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.cur, self.pending, self.ri = [], {}, 0
        elif tag == "tr" and self.cur is not None and self.depth == 1:
            self.row = []
        elif tag in ("td", "th") and self.row is not None and self.depth == 1:
            def num(x):
                try:
                    return max(1, int(x))
                except (TypeError, ValueError):
                    return 1
            self.cell = {"txt": [], "rs": num(a.get("rowspan")), "cs": num(a.get("colspan"))}

    def handle_data(self, d):
        if self.cell is not None:
            self.cell["txt"].append(d)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self._flush()
            self.row = None
        elif tag == "table":
            if self.depth == 1 and self.cur is not None:
                self.tables.append(self.cur)
                self.cur = None
            self.depth = max(0, self.depth - 1)

    def _flush(self):
        out, ci = [], 0
        it = iter(self.row)
        while True:
            while (self.ri, ci) in self.pending:
                out.append(self.pending.pop((self.ri, ci)))
                ci += 1
            c = next(it, None)
            if c is None:
                break
            txt = html.unescape("".join(c["txt"])).strip()
            for k in range(c["cs"]):
                out.append(txt)
                for r in range(1, c["rs"]):
                    self.pending[(self.ri + r, ci + k)] = txt
            ci += c["cs"]
        self.cur.append(out)
        self.ri += 1


def fetch_html(page):
    cache = os.path.join(HERE, "raw", f"wiki_{page}.html")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    if os.path.exists(cache):
        return open(cache).read()
    delay = 3
    for _ in range(5):
        r = requests.get(API, params={"action": "parse", "page": page,
                                      "prop": "text", "format": "json"},
                         headers=UA, timeout=90)
        if r.status_code == 200:
            t = r.json()["parse"]["text"]["*"]
            with open(cache, "w") as f:
                f.write(t)
            return t
        print(f"  retry {page}: HTTP {r.status_code}")
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError(f"fetch failed: {page}")


# 駅名セルには注記が付く（庄内駅#、川西能勢口駅‡[* 1]、山本駅（平井）など）ので
# 「駅」で終わることを要求すると行がごっそり落ちる。後続が注記・括弧・空白・行末なら駅名とみなす。
# 「天王寺駅前」のような停留場名を誤って拾わないよう、直後が「前」の場合は除く。
_STA = re.compile(r"^(.+?)駅(?![前])(?:[#‡*＊※]|\s|（|\(|\[|$)")


def extract(page):
    g = Grid()
    g.feed(fetch_html(page))
    best = None
    for t in g.tables:
        marks = sum(1 for row in t for c in row if c in STOP or c in PASS)
        stations = sum(1 for row in t for c in row if _STA.match(c))
        if marks >= 20 and stations >= 8 and (best is None or marks > best[0]):
            best = (marks, t)
    if best is None:
        return [], []
    tab = best[1]
    width = max(len(r) for r in tab)
    col_sta = max(range(width),
                  key=lambda c: sum(1 for r in tab if c < len(r) and _STA.match(r[c])))
    cls_cols = []
    for c in range(width):
        n = sum(1 for r in tab if c < len(r) and (r[c] in STOP or r[c] in PASS))
        if n >= 8:
            head = ""
            for r in tab:
                if c < len(r) and r[c] and r[c] not in STOP and r[c] not in PASS \
                        and not _STA.match(r[c]):
                    head = re.sub(r"\s+", "", r[c])
                    break
            cls_cols.append((c, head))
    rows = []
    for r in tab:
        if col_sta >= len(r):
            continue
        m = _STA.match(r[col_sta])
        if not m:
            continue
        rows.append((m.group(1).strip(), {h: (c < len(r) and r[c] in STOP)
                                          for c, h in cls_cols}))
    return [h for _, h in cls_cols], rows


def main():
    out = {}
    for page, (line_key, drop) in PAGES.items():
        classes, rows = extract(page)
        if not classes:
            print(f"★ {page}: 表を特定できず")
            continue
        pats = {}
        for cls in classes:
            if not cls or cls in drop:
                continue
            stops = [nm for nm, mk in rows if mk.get(cls)]
            if len(stops) >= 3:
                pats[cls] = stops
        print(f"{page}: 駅{len(rows)} 列見出し={classes}")
        for c, s in pats.items():
            print(f"    {c}: {len(s)}駅  {' '.join(s[:8])}…")
        out[page] = {"line_key": line_key,
                     "source": f"https://ja.wikipedia.org/wiki/{page}",
                     "patterns": pats}
    path = os.path.join(HERE, "express_patterns.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"-> {path}")


if __name__ == "__main__":
    main()
