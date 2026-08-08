const { chromium } = require('playwright'); const fs=require('fs');
const list=JSON.parse(fs.readFileSync('/home/user/osm/score/list.json','utf8'));
(async()=>{const b=await chromium.launch({args:['--no-sandbox']});
for(const [name,file] of list){
  let svg=fs.readFileSync(file,'utf8').replace(/width="[^"]*"\s*height="[^"]*"/,'width="480" height="480"');
  const p=await b.newPage({viewport:{width:520,height:520},deviceScaleFactor:1});
  await p.setContent('<body style="margin:0;background:#fff">'+svg+'</body>');
  await p.waitForTimeout(700);
  await p.locator('svg').screenshot({path:`/home/user/osm/score/${name}.png`});
  await p.close();
}
await b.close();console.log('rendered',list.length);})();
