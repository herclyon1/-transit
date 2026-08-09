# -*- coding: utf-8 -*-
"""核对東亜配色：① 每个色是不是该国国旗的主色 ② 真正接壤的邻国之间分不分得开。
   色差用 CIE76 ΔE（Lab 空间），ΔE<15 在地图上就容易看混。"""
import re, math, json, sys

src=open("/home/user/-transit/quiz/map.html",encoding="utf-8").read()
m=re.search(r'const EAC=\[(.*?)\];', src, re.S)
pairs=re.findall(r'"([A-Z]{3})","(#[0-9A-Fa-f]{6})"', m.group(1))
rus=re.search(r'const RUS="(#[0-9A-Fa-f]{6})"', src).group(1)
pal=dict(pairs); pal["RUS"]=rus

def lab(h):
    r,g,b=[int(h[i:i+2],16)/255 for i in (1,3,5)]
    f=lambda c: c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
    r,g,b=f(r),f(g),f(b)
    X=(.4124*r+.3576*g+.1805*b)/.95047; Y=.2126*r+.7152*g+.0722*b; Z=(.0193*r+.1192*g+.9505*b)/1.08883
    t=lambda v: v**(1/3) if v>.008856 else 7.787*v+16/116
    X,Y,Z=t(X),t(Y),t(Z)
    return (116*Y-16, 500*(X-Y), 200*(Y-Z))
def dE(a,b):
    la,lb=lab(a),lab(b); return math.sqrt(sum((x-y)**2 for x,y in zip(la,lb)))

# 真正接壤（含隔窄海相望）的邻国对
ADJ=[("CHN","PRK"),("CHN","MNG"),("CHN","VNM"),("CHN","LAO"),("CHN","IND"),("CHN","NPL"),
     ("CHN","BTN"),("CHN","MMR"),("CHN","KOR"),("CHN","RUS"),("CHN","TWN"),
     ("PRK","KOR"),("PRK","RUS"),("KOR","JPN"),("JPN","RUS"),("JPN","TWN"),
     ("MNG","RUS"),("CHN","JPN"),("PRK","JPN"),("KHM","VNM"),("MMR","IND"),
     ("PHL","MYS"),("IDN","BRN"),("LKA","MDV"),("TWN","CHN"),("VNM","LAO"),("VNM","KHM"),("LAO","KHM"),("LAO","THA"),("LAO","MMR"),
     ("KHM","THA"),("THA","MMR"),("THA","MYS"),("MYS","BRN"),("MYS","IDN"),("MYS","SGP"),
     ("BRN","IDN"),("IDN","TLS"),("IDN","PNG"),("IDN","PHL"),("PHL","TWN"),
     ("IND","NPL"),("IND","BTN"),("IND","BGD"),("IND","LKA"),("IND","MMR"),
     ("BGD","MMR"),("PLW","FSM"),("PLW","PHL"),("FSM","MHL"),("MNP","PHL"),("MDV","LKA")]
bad=[]
for a,b in ADJ:
    if a not in pal or b not in pal: print("!! 缺色", a, b); continue
    d=dE(pal[a],pal[b])
    if d<15: bad.append((round(d,1),a,pal[a],b,pal[b]))
print("配色项", len(pal), "（含 RUS）")
print("接壤对", len(ADJ), "，ΔE<15 分不开的:", len(bad))
for d,a,ca,b,cb in sorted(bad): print("   ΔE %.1f  %s %s  ↔  %s %s"%(d,a,ca,b,cb))
