# -*- coding: utf-8 -*-
"""把「国家代表色」变成**算出来的**，不掺个人口味：
   取该国国旗，按像素统计各颜色的**面积占比**，占比最大的那个色就是代表色。
   白/黑/灰不算（几乎每面旗都有，且铺在地图上无法区分），从彩色里取最大。
"""
import urllib.request, collections, math, json
from PIL import Image
import io

ISO={"CHN":"cn","JPN":"jp","KOR":"kr","PRK":"kp","MNG":"mn","TWN":"tw","VNM":"vn","LAO":"la",
 "KHM":"kh","THA":"th","MMR":"mm","MYS":"my","SGP":"sg","BRN":"bn","IDN":"id","TLS":"tl",
 "PNG":"pg","PHL":"ph","IND":"in","LKA":"lk","NPL":"np","BTN":"bt","BGD":"bd","PLW":"pw",
 "FSM":"fm","MHL":"mh","MNP":"mp","MDV":"mv","RUS":"ru"}

def fetch(cc):
    for _ in range(3):
        try:
            with urllib.request.urlopen("https://flagcdn.com/w320/%s.png"%cc, timeout=25) as r:
                im=Image.open(io.BytesIO(r.read())).convert("RGBA")
                # 尼泊尔的旗是非矩形，PNG 带透明；直接 convert("RGB") 会把透明区算成颜色
                # （上一版尼泊尔因此算出「绿色 39.5%」这种不存在的结果）。透明像素必须剔除。
                return im
        except Exception: pass
    return None

def hsl(c):
    r,g,b=[x/255 for x in c]; mx,mn=max(r,g,b),min(r,g,b); l=(mx+mn)/2
    s=0 if mx==mn else (mx-mn)/(2-mx-mn if l>.5 else mx+mn)
    return s,l

rows=[]
for iso,cc in ISO.items():
    im=fetch(cc)
    if im is None: print("!! 取不到", iso); continue
    im=im.resize((160,107))
    q=collections.Counter(); tot=0
    for px in im.get_flattened_data():
        if px[3]<200: continue                  # 透明像素不算（尼泊尔旗是非矩形）
        q[tuple(v//24*24 for v in px[:3])]+=1
        tot+=1
    # 占比低于 3% 的当噪声（抗锯齿边、图案细节），否则会捡到泰国旗上那种伪色
    chroma=[(n,c) for c,n in q.items() if hsl(c)[0]>0.22 and 0.12<hsl(c)[1]<0.92 and n/tot>=0.03]
    chroma.sort(reverse=True)
    if not chroma: chroma=[(n,c) for c,n in q.most_common(1)]
    top=[(c,n/tot) for n,c in chroma[:3]]
    rows.append((iso,top))

print("%-5s %-22s %s"%("ISO","面积最大的彩色","次位"))
for iso,top in rows:
    f=lambda t: "#%02X%02X%02X %4.1f%%"%(t[0][0],t[0][1],t[0][2],t[1]*100)
    print("%-5s %-22s %s"%(iso, f(top[0]), " / ".join(f(t) for t in top[1:])))
json.dump({iso:[["#%02X%02X%02X"%c, round(p,4)] for c,p in top] for iso,top in rows},
          open("flag_top.json","w"), ensure_ascii=False, indent=0)
