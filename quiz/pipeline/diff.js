const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch({args:['--no-sandbox']});
const p=await b.newPage({viewport:{width:140,height:100},deviceScaleFactor:1});
await p.setContent('<body style="margin:0;background:#fff">'+require('fs').readFileSync('/home/user/osm/clawd_final.svg','utf8')+'</body>');
await p.waitForTimeout(300);
await p.locator('svg').screenshot({path:'/home/user/osm/mine.png'});
await b.close();console.log('ok');})();
