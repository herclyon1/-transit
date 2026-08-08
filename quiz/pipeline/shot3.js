const { chromium } = require('playwright');
const VIEWS = [
  ['overview', 112, 22, 2.2],
  ['yalu',     124.4, 40.1, 9.5],   // 中朝边界·鸭绿江
  ['philippines', 122.0, 12.0, 6.0] // 菲律宾水系
];
(async () => {
  const b = await chromium.launch({args:['--no-sandbox']});
  const p = await b.newPage({viewport:{width:390,height:844},deviceScaleFactor:2});
  const errs=[]; p.on('pageerror', e=>errs.push(String(e).slice(0,160)));
  p.on('console', m=>{ if(m.type()==='error') errs.push(m.text().slice(0,160)); });
  await p.goto('http://127.0.0.1:8770/quiz/ml-proto.html', {waitUntil:'load', timeout:60000});
  await p.waitForTimeout(6000);
  for (const [name, lng, lat, z] of VIEWS) {
    await p.evaluate(([lng,lat,z]) => { window.__map.jumpTo({center:[lng,lat], zoom:z}); }, [lng,lat,z]);
    await p.waitForTimeout(6000);
    await p.screenshot({path:`/home/user/osm/v_${name}.png`});
    console.log('shot', name);
  }
  await b.close();
  console.log('错误:', errs.length ? errs.slice(0,4).join(' | ') : '无');
})();
