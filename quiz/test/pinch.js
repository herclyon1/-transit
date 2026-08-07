// 真实双指捏合 (CDP Input.dispatchTouchEvent) + 抖动检测:
// 手指只往外张 => k 必须单调增。若出现"增-减-增"回跳, 即用户所说的抖动。
const { chromium } = require('playwright'); const path=require('path');
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium',args:['--no-sandbox']});
  const ctx=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
  const p=await ctx.newPage(); const CDN=path.join(__dirname,'cdn'); const errs=[];
  p.on('pageerror',e=>errs.push(e.message.slice(0,140)));
  await p.route('**cdnjs.cloudflare.com/**d3**',r=>r.fulfill({path:path.join(CDN,'d3.min.js'),contentType:'application/javascript'}));
  await p.route('**cdnjs.cloudflare.com/**topojson**',r=>r.fulfill({path:path.join(CDN,'topojson.min.js'),contentType:'application/javascript'}));
  await p.route('**jsdelivr.net/**',r=>r.fulfill({path:path.join(CDN,'topo.json'),contentType:'application/json'}));
  const cdp=await ctx.newCDPSession(p); await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  await p.goto(process.argv[2]); await p.waitForTimeout(5000);
  await p.click('button[data-m="kyoeiken"]',{timeout:120000}); await p.waitForTimeout(6000);
  await p.evaluate(()=>{ window.__log=[];
    const o=svg.node(); const rec=()=>{const t=d3.zoomTransform(o);
      window.__log.push({t:performance.now(),k:t.k,x:t.x,y:t.y,
        cvt:document.getElementById('eaCv').style.transform||''}); requestAnimationFrame(rec);}; requestAnimationFrame(rec); });
  const T=(type,pts)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints:pts.map((q,i)=>({x:q[0],y:q[1],id:i,radiusX:12,radiusY:12,force:1}))});
  const cx=195,cy=430;
  await T('touchStart',[[cx-40,cy],[cx+40,cy]]);
  for(let i=1;i<=26;i++){ const d=40+i*11; await T('touchMove',[[cx-d,cy],[cx+d,cy]]); await p.waitForTimeout(30); }
  await T('touchEnd',[]);
  await p.waitForTimeout(1500);
  const log=await p.evaluate(()=>window.__log);
  const ks=log.map(o=>o.k);
  let back=0,worst=0;
  for(let i=1;i<ks.length;i++){ if(ks[i]<ks[i-1]-1e-6){ back++; worst=Math.max(worst,(ks[i-1]-ks[i])/ks[i-1]); } }
  const cvts=new Set(log.map(o=>o.cvt));
  console.log('捏合: k '+ks[0].toFixed(2)+' -> '+ks[ks.length-1].toFixed(2)+'  帧数'+ks.length);
  console.log('k 回跳次数: '+back+(back?'  最大回跳幅度 '+(worst*100).toFixed(1)+'%  ❌抖动':'  ✅单调无抖'));
  console.log('画布CSS变换取值集合:',[...cvts].map(v=>v||'(空)').join(' | '));
  console.log('落定 tier='+await p.evaluate(()=>eaTier)+' k='+await p.evaluate(()=>+d3.zoomTransform(svg.node()).k.toFixed(1))+' low='+await p.evaluate(()=>document.getElementById('eaCv')._low));
  // 帧间隔
  const dts=[];for(let i=1;i<log.length;i++)dts.push(log[i].t-log[i-1].t);
  dts.sort((a,b)=>a-b);
  console.log('捏合帧时 p50='+dts[Math.floor(dts.length/2)].toFixed(0)+'ms p90='+dts[Math.floor(dts.length*0.9)].toFixed(0)+'ms max='+dts[dts.length-1].toFixed(0)+'ms');
  console.log('errors:',errs.length?errs:'none');
  await p.screenshot({path:'pinch.png'});
  await b.close();
})();
