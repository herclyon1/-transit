# -*- coding: utf-8 -*-
"""国家代表色**从外部权威来源取**，不再自己从国旗推。
   来源：Wikipedia「National colours」——各国自己指定的国家代表色（多数有法源或奥委会/体育协会依据）。
   取法：读该国那一行的**文字**（如中国「Red and yellow」），取第一个有彩的颜色词；
        再从同一行的色块里挑与该词最接近的那个 hex。文字里没有色块就用该颜色词的标准色。
   —— 依据完全来自条目本身，我不做主观选择。
"""
import re, html, json, math
s = open("natcol.html", encoding="utf-8", errors="replace").read()

PAT = {"CHN":r"China\b(?!\s*\()","JPN":r"Japan\b","KOR":r"Korea, South","PRK":r"Korea, North",
 "MNG":r"Mongolia\b","TWN":r"Taiwan\b","VNM":r"Vietnam\b","LAO":r"Laos\b","KHM":r"Cambodia\b",
 "THA":r"Thailand\b","MMR":r"(Myanmar|Burma)\b","MYS":r"Malaysia\b","SGP":r"Singapore\b",
 "BRN":r"Brunei\b","IDN":r"Indonesia\b","TLS":r"(East Timor|Timor-Leste)","PNG":r"Papua New Guinea",
 "PHL":r"Philippines\b","IND":r"India\b(?!n Ocean)","LKA":r"Sri Lanka","NPL":r"Nepal\b","BTN":r"Bhutan\b",
 "BGD":r"Bangladesh\b","PLW":r"Palau\b","FSM":r"Micronesia\b","MHL":r"Marshall Islands",
 "MNP":r"Northern Mariana","MDV":r"Maldives\b","RUS":r"Russia\b"}
WORD = {"red":"#D42B2B","crimson":"#C2143C","maroon":"#8C2331","scarlet":"#D02A20",
 "blue":"#1F4FA8","azure":"#2E7BD6","green":"#1F8A4C","yellow":"#E8C42A","gold":"#D9AC2A",
 "orange":"#E07A20","saffron":"#E68B2C","purple":"#7A3F9E","violet":"#7A3F9E","pink":"#D96E92",
 "black":"#2A2A2A","white":"#F2F2F2","silver":"#BFC4C9","verdigris":"#43B3AE","turquoise":"#40B5A8"}
ACHROM = {"white","black","silver"}

def lab(h):
    r,g,b=[int(h[i:i+2],16)/255 for i in (1,3,5)]
    f=lambda c: c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
    r,g,b=f(r),f(g),f(b)
    X=(.4124*r+.3576*g+.1805*b)/.95047;Y=.2126*r+.7152*g+.0722*b;Z=(.0193*r+.1192*g+.9505*b)/1.08883
    t=lambda v: v**(1/3) if v>.008856 else 7.787*v+16/116
    X,Y,Z=t(X),t(Y),t(Z); return (116*Y-16,500*(X-Y),200*(Y-Z))
def dE(a,b): return math.sqrt(sum((x-y)**2 for x,y in zip(lab(a),lab(b))))

out={}
for r in re.split(r'<tr\b', s):
    txt = html.unescape(re.sub(r'<[^>]+>',' ', r))
    txt = re.sub(r'^\s*(id="\w+")?\s*>?\s*','', re.sub(r'\s+',' ',txt)).strip()
    if not txt: continue
    hexes = re.findall(r'\{"wt":"(#[0-9A-Fa-f]{6})"\}', r)
    for iso,pat in PAT.items():
        if iso in out: continue
        m = re.match(r'\s*'+pat, txt)          # 必须**行首**就是国名，避免误匹配正文
        if not m: continue
        words = re.findall(r'\b('+"|".join(WORD)+r')\b', txt.lower())
        chroma = [w for w in words if w not in ACHROM]
        first = chroma[0] if chroma else (words[0] if words else None)
        if not first: continue
        target = WORD[first]
        # 色块要跟文字里的颜色词对得上才用。中国那行文字写「Red and yellow」，
        # 但抓到的色块只有黄和深蓝，硬挑最近的会挑成深蓝——那显然不是中国的代表色。
        pick, src = target, "word"
        if hexes:
            best = min(hexes, key=lambda h: dE(h,target))
            if dE(best,target) < 40: pick, src = best, "swatch"
        # 第二顺位的颜色词也留下：万一相邻国靠深浅也分不开，就退到它自己声明的第二色
        second = None
        for w in chroma[1:]:
            if w != first: second = w; break
        out[iso] = {"word":first, "hex":pick, "src":src,
                    "word2":second, "hex2":WORD[second] if second else None, "line":txt[:64]}
print("从条目拿到 %d / %d"%(len(out), len(PAT)))
for iso in PAT:
    v = out.get(iso)
    print("  %-5s %-8s %-9s %s"%(iso, v["hex"] if v else "—", v["word"] if v else "", (v["line"] if v else "（条目里没有这一国）")))
json.dump(out, open("natcol2.json","w"), ensure_ascii=False, indent=0)
