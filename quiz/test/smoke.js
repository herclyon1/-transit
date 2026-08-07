const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath:'/opt/pw-browsers/chromium', args:['--no-sandbox'] });
  const p = await b.newPage({ viewport:{width:1280,height:900} });
  const errs=[]; p.on('pageerror', e=>errs.push(e.message));
  const CDN = path.join(__dirname,'cdn');
  await p.route('**cdnjs.cloudflare.com/**d3**', r=>r.fulfill({path:path.join(CDN,'d3.min.js'),contentType:'application/javascript'}));
  await p.route('**cdnjs.cloudflare.com/**topojson**', r=>r.fulfill({path:path.join(CDN,'topojson.min.js'),contentType:'application/javascript'}));
  await p.route('**jsdelivr.net/**', r=>r.fulfill({path:path.join(CDN,'topo.json'),contentType:'application/json'}));
  await p.goto(process.argv[2].startsWith('http')?process.argv[2]:'file://'+path.resolve(process.argv[2]));
  await p.waitForTimeout(5000);
  const out={};
  for(const m of ['browse','dainippon','kyoeiken','quiz','campaign']){
    await p.click(`button[data-m="${m}"]`).catch(e=>errs.push('click '+m+': '+e.message));
    await p.waitForTimeout(2500);
    const st = await p.evaluate(()=>{
      const wc=document.querySelectorAll('.wc').length, pref=document.querySelectorAll('.pref').length;
      let land='n/a',halo='n/a'; try{land=gLandBg.style('display');}catch(e){} try{halo=gHalo.style('display');}catch(e){}
      return {wc,pref,land,halo};
    });
    out[m]=st;
  }
  console.log('MODES:', JSON.stringify(out,null,1));
  console.log('PAGE ERRORS:', errs.length?errs:'none');
  await b.close();
})();
