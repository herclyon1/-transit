# 按参考图实测出的几何生成 Claw'd，并与参考图做像素比对。
SVG = '''<svg viewBox="0 0 12 8" width="120" height="80" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">
  <g fill="#D77656">
    <rect x="2" y="0" width="8" height="6"/>
    <rect x="0" y="2" width="2" height="2"/>
    <rect x="10" y="2" width="2" height="2"/>
    <rect x="2" y="6" width="1" height="2"/>
    <rect x="4" y="6" width="1" height="2"/>
    <rect x="7" y="6" width="1" height="2"/>
    <rect x="9" y="6" width="1" height="2"/>
  </g>
  <rect x="3" y="1" width="1" height="1" fill="#000"/>
  <rect x="8" y="1" width="1" height="1" fill="#000"/>
</svg>'''
open('/home/user/-transit/_clawd_test.svg','w').write(SVG)
open('/home/user/osm/clawd_final.svg','w').write(SVG)
print("written")
