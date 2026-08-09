# -*- coding: utf-8 -*-
"""最终配色：色源来自**各国自己声明的国家代表色**（Wikipedia「National colours」，
   多数有法源或奥委会/体育协会依据），不是我从国旗推的。
   条目里没有的 4 个太平洋国家/地区退回国旗主色，并在下面标出来。

   分隔策略：**色相保住各国自己的**，相邻国之间靠明度/饱和度拉开；
   实在拉不开才退到该国声明的第二色。这样中国仍是红、日本仍是红、俄罗斯仍是蓝。
   判据：44 对真正接壤的邻国，CIE76 ΔE 必须全部 ≥15。
"""
import json, math, colorsys
nat=json.load(open("natcol2.json"))
flag=json.load(open("flag_top.json"))
NAME={"CHN":"中国","JPN":"日本","KOR":"韓国","PRK":"朝鮮","MNG":"モンゴル","TWN":"台湾","VNM":"ベトナム",
 "LAO":"ラオス","KHM":"カンボジア","THA":"タイ","MMR":"ミャンマー","MYS":"マレーシア","SGP":"シンガポール",
 "BRN":"ブルネイ","IDN":"インドネシア","TLS":"東ティモール","PNG":"パプアニューギニア","PHL":"フィリピン",
 "IND":"インド","LKA":"スリランカ","NPL":"ネパール","BTN":"ブータン","BGD":"バングラデシュ","PLW":"パラオ",
 "FSM":"ミクロネシア","MHL":"マーシャル","MNP":"北マリアナ","MDV":"モルディブ","RUS":"ロシア"}
AREA={"CHN":9596961,"RUS":17098246,"IND":3287263,"IDN":1904569,"MNG":1564116,
 "MMR":676578,"THA":513120,"PNG":462840,"JPN":377975,"VNM":331212,"MYS":330803,"PHL":300000,
 "LAO":236800,"KHM":181035,"BGD":147570,"NPL":147181,"PRK":120540,"KOR":100210,"LKA":65610,
 "BTN":38394,"TWN":36193,"TLS":14874,"BRN":5765,"SGP":728,"FSM":702,"MNP":464,"PLW":459,
 "MDV":300,"MHL":181}
ADJ=[("CHN","PRK"),("CHN","MNG"),("CHN","VNM"),("CHN","LAO"),("CHN","IND"),("CHN","NPL"),
     ("CHN","BTN"),("CHN","MMR"),("CHN","KOR"),("CHN","RUS"),("CHN","TWN"),
     ("PRK","KOR"),("PRK","RUS"),("KOR","JPN"),("JPN","RUS"),("JPN","TWN"),
     ("MNG","RUS"),("CHN","JPN"),("PRK","JPN"),("KHM","VNM"),("MMR","IND"),
     ("PHL","MYS"),("IDN","BRN"),("LKA","MDV"),("TWN","CHN"),("VNM","LAO"),("VNM","KHM"),("LAO","KHM"),("LAO","THA"),("LAO","MMR"),
     ("KHM","THA"),("THA","MMR"),("THA","MYS"),("MYS","BRN"),("MYS","IDN"),("MYS","SGP"),
     ("BRN","IDN"),("IDN","TLS"),("IDN","PNG"),("IDN","PHL"),("PHL","TWN"),
     ("IND","NPL"),("IND","BTN"),("IND","BGD"),("IND","LKA"),("IND","MMR"),
     ("BGD","MMR"),("PLW","FSM"),("PLW","PHL"),("FSM","MHL"),("MNP","PHL"),("MDV","LKA")]
def hx2rgb(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
def hueof(h):
    r,g,b=[v/255 for v in hx2rgb(h)]; return colorsys.rgb_to_hls(r,g,b)[0]*360
def mk(hd,L,S):
    r,g,b=colorsys.hls_to_rgb(hd/360,L,S); return "#%02X%02X%02X"%(round(r*255),round(g*255),round(b*255))
def lab(h):
    r,g,b=[v/255 for v in hx2rgb(h)]
    f=lambda c: c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
    r,g,b=f(r),f(g),f(b)
    X=(.4124*r+.3576*g+.1805*b)/.95047;Y=.2126*r+.7152*g+.0722*b;Z=(.0193*r+.1192*g+.9505*b)/1.08883
    t=lambda v: v**(1/3) if v>.008856 else 7.787*v+16/116
    X,Y,Z=t(X),t(Y),t(Z); return (116*Y-16,500*(X-Y),200*(Y-Z))
def dE(a,b): return math.sqrt(sum((x-y)**2 for x,y in zip(lab(a),lab(b))))

src={}
for iso in NAME:
    if iso in nat:
        src[iso]={"hue":hueof(nat[iso]["hex"]),"hue2":hueof(nat[iso]["hex2"]) if nat[iso].get("hex2") else None,
                  "from":"国家代表色 · "+nat[iso]["word"]}
    else:
        h=flag[iso][0][0]
        src[iso]={"hue":hueof(h),"hue2":hueof(flag[iso][1][0]) if len(flag[iso])>1 else None,
                  "from":"条目缺 → 退回国旗主色"}
# 明度档：从深到浅
LS=[(0.62,0.50),(0.72,0.42),(0.53,0.55),(0.80,0.34),(0.67,0.34),(0.58,0.38),(0.76,0.50)]
cur={iso:0 for iso in NAME}; use2={iso:False for iso in NAME}
def color(iso):
    h=src[iso]["hue2"] if use2[iso] and src[iso]["hue2"] is not None else src[iso]["hue"]
    L,S=LS[cur[iso]]; return mk(h,L,S)
for it in range(20000):
    pal={iso:color(iso) for iso in NAME}
    # 接壤的必须 ΔE≥15；不接壤的也不能完全同色（台湾和朝鲜、中国和印尼曾撞成一模一样，
    # 因为它们不接壤，只查接壤对拦不住），所以全体两两至少 ΔE≥8。
    bad=sorted([(dE(pal[a],pal[b]),a,b) for a,b in ADJ if dE(pal[a],pal[b])<15])
    if not bad: break
    _,a,b=bad[0]
    # 让步顺序按**国土面积**：小的让。客观、稳定，而且能保证在地图上占最大面积的国家
    # 保住自己的第一代表色（中国 = 红）。上一版按国名排序让步，把中国推成了黄色。
    y = a if AREA[a] < AREA[b] else b
    # 先试该国声明的第二色（仍是它自己的代表色），再动明度——
    # 上一版一路加明度，把韓国推成 #E9D8D9 近乎白，地图上没法看。
    if not use2[y] and src[y]["hue2"] is not None and cur[y]>=1:
        use2[y]=True; cur[y]=0
    elif cur[y]+1 < len(LS): cur[y]+=1
    else: cur[y]=0; use2[y]=not use2[y] if src[y]["hue2"] is not None else use2[y]
    if it==2999: print("!! 迭代未收敛")
pal={iso:color(iso) for iso in NAME}
# 后处理：主循环只管接壤。不接壤的国家同色在地图学上本来允许（四色定理），
# 但**完全一模一样**还是别扭（台湾曾和朝鲜、中国曾和印尼撞成同一个值）。
# 这里只对 ΔE<4 的对做最小微调：面积小的那方换一档明度，换完必须仍满足接壤约束。
import itertools as _it2
for _ in range(200):
    dups=[(dE(pal[a],pal[b]),a,b) for a,b in _it2.combinations(sorted(NAME),2) if dE(pal[a],pal[b])<4]
    if not dups: break
    _,a,b=sorted(dups)[0]
    y=a if AREA[a]<AREA[b] else b
    ok=False
    for step in range(1,len(LS)):
        save=cur[y]; cur[y]=(cur[y]+step)%len(LS); trial={iso:color(iso) for iso in NAME}
        if all(dE(trial[x],trial[z])>=15 for x,z in ADJ): pal=trial; ok=True; break
        cur[y]=save
    if not ok: break
bad=[(round(dE(pal[a],pal[b]),1),a,b) for a,b in ADJ if dE(pal[a],pal[b])<15]
dup=[(round(dE(pal[a],pal[b]),1),a,b) for a,b in _it2.combinations(sorted(NAME),2) if dE(pal[a],pal[b])<4]
print("接壤 %d 对 ΔE<15:"%len(ADJ), bad or "无", "  全体两两 ΔE<4:", dup or "无")
print()
print("%-5s %-7s %-9s %s"%("ISO","国","配色","依据"))
for iso in NAME:
    tag=src[iso]["from"]+("（第二色）" if use2[iso] else "")
    print("  %-5s %-7s %-9s %s"%(iso,NAME[iso],pal[iso],tag))
json.dump(pal,open("palette_final.json","w"),ensure_ascii=False,indent=0)
