const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({args:['--no-sandbox']});
  const p = await b.newPage({viewport:{width:390,height:844},deviceScaleFactor:2});
  const errs=[], reqs=[];
  p.on('console', m => { if(m.type()==='error') errs.push(m.text().slice(0,200)); });
  p.on('pageerror', e => errs.push('PAGEERROR '+String(e).slice(0,200)));
  p.on('response', r => { const u=r.url(); if(u.includes('.pmtiles')) reqs.push(r.status()); });
  await p.goto('http://127.0.0.1:8770/quiz/ml-proto.html', {waitUntil:'load', timeout:60000});
  await p.waitForTimeout(9000);
  await p.screenshot({path:'/home/user/osm/shot_overview.png'});
  // 放大到中朝边界
  await p.evaluate(()=>{ window.__m && 0; });
  await p.evaluate(()=>{ const m=document.querySelector('#map'); });
  await p.evaluate(()=>{ /* 用 maplibre 实例 */ });
  await b.close();
  console.log('pmtiles 请求状态:', JSON.stringify(reqs.slice(0,6)), '共', reqs.length);
  console.log('控制台错误:', errs.length ? errs.slice(0,5).join(' | ') : '无');
})();
