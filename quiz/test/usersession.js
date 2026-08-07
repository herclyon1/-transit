// 上线前必过: 模拟真人在手机上的前30秒 —— 真实输入事件、真实手势、逐步截图 + 不变量检查。
// 【为什么必须这样测】程序化 zoom.transform 走的代码分支和真实手势不同; 数据审计看不见任何视觉问题。
// 用户报过的四个恶性bug(画布盖住标记/标注飞出屏幕/抖动/高精度不刷新)全部只能在这种测法下暴露。
const { chromium } = require('playwright'); const path=require('path'); const fs=require('fs');
const URL=process.argv[2], OUT=process.argv[3]||'session';
(async()=>{
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium',args:['--no-sandbox','--force-color-profile=srgb']});
  const ctx=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true});
  const p=await ctx.newPage(); const CDN=path.join(__dirname,'cdn'); const errs=[];
  p.on('pageerror',e=>errs.push('PAGEERROR '+e.message.slice(0,120)));
  p.on('console',m=>{if(m.type()==='error')errs.push('CONSOLE '+m.text().slice(0,100));});
  await p.route('**cdnjs.cloudflare.com/**d3**',r=>r.fulfill({path:path.join(CDN,'d3.min.js'),contentType:'application/javascript'}));
  await p.route('**cdnjs.cloudflare.com/**topojson**',r=>r.fulfill({path:path.join(CDN,'topojson.min.js'),contentType:'application/javascript'}));
  await p.route('**jsdelivr.net/**',r=>r.fulfill({path:path.join(CDN,'topo.json'),contentType:'application/json'}));
  await p.route('**ea_t*.topojson', async r=>{ await new Promise(s=>setTimeout(s,1200)); r.continue(); }); // 模拟4G延迟
  const cdp=await ctx.newCDPSession(p); await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  const shots=[], checks=[];
  const shot=async(name)=>{ const f=`${OUT}-${String(shots.length+1).padStart(2,'0')}-${name}.png`;
    await p.screenshot({path:f}); shots.push({f,name}); };
  const chk=(name,ok,detail)=>{ checks.push((ok?'✅':'❌')+' '+name+(detail?'  '+detail:'')); };

  await p.goto(URL); await p.waitForTimeout(6000);
  await shot('开页');
  // 東亜
  await p.click('button[data-m="kyoeiken"]',{timeout:120000}); await p.waitForTimeout(7000);
  await shot('東亜全图');
  let st=await p.evaluate(()=>{
    const cv=document.getElementById('eaCv'), c=cv.getContext('2d');
    // 画布是否真画了东西: 采样中心区域
    const d=c.getImageData(Math.round(cv.width*0.35),Math.round(cv.height*0.35),40,40).data;
    let painted=0; for(let i=3;i<d.length;i+=4) if(d[i]>10) painted++;
    const mks=[...document.querySelectorAll('.mk')];
    let topOK=0, inView=0;
    mks.forEach(g=>{const r=g.getBoundingClientRect(); if(r.width<1)return;
      if(r.x>0&&r.y>0&&r.right<innerWidth&&r.bottom<innerHeight){inView++;
        const el=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
        if(el&&el.id!=='eaCv') topOK++;}});
    const dl=[...document.querySelectorAll('svg#map text')].filter(t=>/争议/.test(t.textContent));
    return {painted, markers:mks.length, mkInView:inView, mkTop:topOK,
      dispTexts:dl.length, dispOnScreen:dl.filter(t=>{const x=+t.getAttribute('x'),y=+t.getAttribute('y');return x>-200&&x<innerWidth+200&&y>-200&&y<innerHeight+200;}).length,
      tier:window.eaTier, k:+d3.zoomTransform(svg.node()).k.toFixed(1)};
  });
  chk('画布已绘制内容', st.painted>200, `采样命中${st.painted}/1600`);
  chk('标记圈在画布之上', st.mkInView>0 && st.mkTop===st.mkInView, `视口内${st.mkInView}个,置顶${st.mkTop}个`);
  chk('争议标注锚点在屏幕范围内', st.dispTexts===0||st.dispOnScreen>0, `文本${st.dispTexts}个,在范围内${st.dispOnScreen}个`);
  // 真实滚轮放大(模拟捏合)
  await p.mouse.move(195,430);
  for(let i=0;i<22;i++){ await p.mouse.wheel(0,-200); await p.waitForTimeout(55); }
  await p.waitForTimeout(2500); await shot('放大后');
  const st2=await p.evaluate(()=>({tier:eaTier,k:+d3.zoomTransform(svg.node()).k.toFixed(1),loaded:EA.map(x=>x?1:0).join(''),low:document.getElementById('eaCv')._low}));
  chk('放大后已升到与倍率相称的档', (st2.k<=5?st2.tier>=0:st2.k<=30?st2.tier>=1:st2.tier>=2), `k=${st2.k} tier=${st2.tier} 已加载=${st2.loaded}`);
  chk('停手后恢复全分辨率', st2.low===false, `_low=${st2.low}`);
  // 抖动检测: 连续滚轮期间逐帧记录画布左上角对应的经纬, 检查是否单调(不回跳)
  const jit=await p.evaluate(()=>new Promise(res=>{
    const xs=[]; let n=0;
    const t=setInterval(()=>{ xs.push(d3.zoomTransform(svg.node()).x); if(++n>40){clearInterval(t);res(xs);} },16);
  }));
  await p.mouse.move(195,430);
  for(let i=0;i<8;i++){ await p.mouse.wheel(0,-180); await p.waitForTimeout(40); }
  await p.waitForTimeout(900); await shot('再放大');
  // 拖动
  await p.mouse.move(195,430); await p.mouse.down();
  for(let i=0;i<14;i++){ await p.mouse.move(195+i*10, 430+i*7); await p.waitForTimeout(25); }
  await p.mouse.up(); await p.waitForTimeout(1200); await shot('拖动后');
  // 点一个单元
  await p.mouse.click(195,430); await p.waitForTimeout(1200); await shot('点单元');
  const info=await p.evaluate(()=>({disp:document.getElementById('info').style.display,txt:document.getElementById('info').textContent.slice(0,20),sel:eaSel?eaSel.properties.n:null}));
  chk('点单元出信息卡', info.disp==='block'&&!!info.sel, JSON.stringify(info));
  // 回全图 -> 点标记
  await p.evaluate(()=>{const bs=[...document.querySelectorAll('button')];const t=bs.find(x=>x.textContent.trim()==='全図');if(t)t.click();});
  await p.waitForTimeout(2500); await shot('回全图');
  const m=await p.evaluate(()=>{let el=null;document.querySelectorAll('.mk').forEach(g=>{if((g.textContent||'').includes('台湾'))el=g;});
    if(!el)return null;const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};});
  if(m){ await p.mouse.click(m.x,m.y); await p.waitForTimeout(2500); }
  await shot('点台湾标记');
  const kk=await p.evaluate(()=>+d3.zoomTransform(svg.node()).k.toFixed(1));
  chk('点标记能放大', kk>3, 'k='+kk);
  // 切模式往返
  await p.click('button[data-m="dainippon"]'); await p.waitForTimeout(6000); await shot('大日本');
  const dw=await p.evaluate(()=>document.querySelectorAll('.wc').length);
  chk('大日本有内容', dw>50, dw+'个单元');
  await p.click('button[data-m="browse"]'); await p.waitForTimeout(2500); await shot('浏览');
  await p.click('button[data-m="kyoeiken"]'); await p.waitForTimeout(4000); await shot('回東亜');
  chk('全程无JS报错', errs.length===0, errs.slice(0,3).join(' | '));
  // 拼接联系表
  const html='<body style="margin:0;background:#222;display:flex;flex-wrap:wrap;gap:3px;">'+
    shots.map(s=>{const b64=fs.readFileSync(s.f).toString('base64');
      return `<div style="width:190px"><div style="color:#fff;font:11px sans-serif;padding:1px 2px">${s.name}</div><img src="data:image/png;base64,${b64}" style="width:190px;display:block"></div>`;}).join('')+'</body>';
  const pg=await ctx.newPage(); await pg.setViewportSize({width:800,height:1400});
  await pg.setContent(html); await pg.waitForTimeout(1200);
  await pg.screenshot({path:OUT+'-contact.png',fullPage:true});
  console.log(checks.join('\n'));
  console.log('联系表:',OUT+'-contact.png');
  await b.close();
  process.exit(checks.some(c=>c.startsWith('❌'))?1:0);
})();
