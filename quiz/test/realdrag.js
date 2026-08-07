// 真实拖动帧时测量: 页面内 rAF 记录, Playwright 驱动真实 mousedown/move/up
const { chromium } = require('playwright'); const path=require('path');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium',args:['--no-sandbox']});
  const ctx=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
  const p=await ctx.newPage(); const CDN=path.join(__dirname,'cdn');
  await p.route('**cdnjs.cloudflare.com/**d3**',r=>r.fulfill({path:path.join(CDN,'d3.min.js'),contentType:'application/javascript'}));
  await p.route('**cdnjs.cloudflare.com/**topojson**',r=>r.fulfill({path:path.join(CDN,'topojson.min.js'),contentType:'application/javascript'}));
  await p.route('**jsdelivr.net/**',r=>r.fulfill({path:path.join(CDN,'topo.json'),contentType:'application/json'}));
  const cdp=await ctx.newCDPSession(p); await cdp.send('Emulation.setCPUThrottlingRate',{rate:+(process.argv[4]||4)});
  await p.goto(process.argv[2]); await p.waitForTimeout(4000);
  await p.click('button[data-m="kyoeiken"]',{timeout:120000}); await p.waitForTimeout(5000);
  const K=+process.argv[3];
  await p.evaluate((K)=>{const w=document.getElementById('stage').clientWidth,h=document.getElementById('stage').clientHeight;
    const pt=projection([104,30.6]);svg.call(zoom.transform,d3.zoomIdentity.translate(w/2-K*pt[0],h/2-K*pt[1]).scale(K));},K);
  await p.waitForTimeout(6000);
  await p.evaluate(()=>{ window.__f=[]; let last=performance.now();
    const rec=()=>{const n=performance.now();window.__f.push(n-last);last=n;requestAnimationFrame(rec);};requestAnimationFrame(rec); });
  await p.mouse.move(195,500); await p.mouse.down();
  await p.evaluate(()=>{ window.__f.length=0; });
  for(let i=0;i<45;i++){ await p.mouse.move(195+Math.sin(i/5)*110, 500+Math.cos(i/6)*130); await p.waitForTimeout(16); }
  const fast=await p.evaluate(()=>{try{return {fast:eaFast,dpr:document.getElementById('eaCv')._dpr};}catch(e){return {fast:'n/a',dpr:'n/a'};}});
  const fr=await p.evaluate(()=>window.__f.slice(3));
  await p.mouse.up(); await p.waitForTimeout(1200);
  const after=await p.evaluate(()=>{try{return {fast:eaFast,dpr:document.getElementById('eaCv')._dpr};}catch(e){return {fast:'n/a',dpr:'n/a'};}});
  fr.sort((a,b)=>a-b); const q=f=>fr[Math.floor(fr.length*f)].toFixed(0);
  console.log('k='+K+'  拖动中 p50='+q(.5)+'ms p90='+q(.9)+'ms max='+fr[fr.length-1].toFixed(0)+
    'ms | 手势内fast='+fast.fast+'(dpr'+fast.dpr+') 松手后fast='+after.fast+'(dpr'+after.dpr+')');
  await b.close();
})();
