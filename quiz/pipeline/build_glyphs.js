// 把字体切成 MapLibre 要的 glyph 分段（每段 256 个码位），**全 256 段一个不少**。
//
// 为什么必须全出：MapLibre 取不到某一段就是 404，而 **404 会让那一整张瓦片解析失败**——
// 不是「这个标注不显示」，是这张瓦片里**所有图层**（连圆点、线都算）全都没有。
// 乌鲁木齐就是这么整片空白的：那边的车站名带维吾尔文（阿拉伯字母，U+0600–06FF），
// 而我们只生成了 88 段、正好没有这一段，于是 glyphs/1536-1791.pbf 404，
// 整个 etr 源在那一带一个要素都出不来（公路在另一个源、且没有文字图层，所以还在，
// 屏幕上就是「只剩黄色的路」）。
//
// 字体里没有的字，生成出来是个空段（几十字节），照样是合法响应，404 就消失了。
// 全 256 段加起来 11MB → 12MB 左右，代价可以忽略。
const fontnik = require('/home/user/osm/node_modules/fontnik');
const fs = require('fs');
const path = require('path');

const SRC = '/home/user/osm/fonts/NotoSansJP.ttf';
const OUT = process.argv[2] || '/home/user/-transit/quiz/glyphs/NotoSansJP Regular';
fs.mkdirSync(OUT, { recursive: true });
const buf = fs.readFileSync(SRC);

let done = 0, made = 0, skipped = 0, failed = 0;
const TOTAL = 256;
for (let i = 0; i < TOTAL; i++) {
  const lo = i * 256, hi = lo + 255;
  const f = path.join(OUT, `${lo}-${hi}.pbf`);
  if (fs.existsSync(f)) { skipped++; done++; continue; }
  fontnik.range({ font: buf, start: lo, end: hi }, (err, data) => {
    if (err) { failed++; }
    else { fs.writeFileSync(f, data); made++; }
    if (++done === TOTAL) {
      console.log(`分段共 ${TOTAL}：新生成 ${made}、已存在 ${skipped}、失败 ${failed}`);
    }
  });
}
