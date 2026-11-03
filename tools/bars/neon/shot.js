const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const logs=[]; page.on('console', m => logs.push(m.type()+': '+m.text())); page.on('pageerror', e => logs.push('ERR: '+e.message));
  await page.goto('http://localhost:8765/index.html?still=1&samples=0&w=1280', { waitUntil: 'load' });
  await page.waitForFunction(() => document.getElementById('load').style.display === 'none' || document.getElementById('load').textContent.startsWith('Ошибка'), null, { timeout: 120000 });
  const frameArg = parseInt(process.argv[2]||'120'); const t0=Date.now();
  await page.evaluate((f) => { if(window.renderOnce) window.renderOnce(f); }, frameArg);
  const hud = await page.evaluate(() => document.getElementById('hud').textContent + ' | ' + document.getElementById('load').textContent);
  console.log('HUD:', hud, 'render ms', Date.now()-t0); console.log(logs.join('\n'));
  await page.screenshot({ path: 'shot_'+frameArg+'.png', clip:{x:0,y:0,width:1280,height:720}, timeout: 300000 }); console.log('shot ms', Date.now()-t0);
  await browser.close();
})();
