const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const logs=[]; page.on('console', m => logs.push(m.type()+': '+m.text())); page.on('pageerror', e => logs.push('ERR: '+e.message));
  const w = process.argv[3]||'960';
  await page.goto('http://localhost:8767/index.html?still=1&samples=0&w='+w, { waitUntil: 'load' });
  await page.waitForFunction(() => document.getElementById('load').style.display === 'none' || document.getElementById('load').textContent.startsWith('Ошибка'), null, { timeout: 180000 });
  const t = parseFloat(process.argv[2]||'3'); const t0=Date.now();
  const setup = process.argv[4]||'';
  await page.evaluate(({t,setup}) => { if(setup) eval(setup); if(window.renderOnce) window.renderOnce(t); }, {t,setup});
  const hud = await page.evaluate(() => document.getElementById('hud').textContent + ' | ' + document.getElementById('load').textContent);
  console.log('HUD:', hud); console.log(logs.join('\n'));
  await page.screenshot({ path: 'cat_'+(process.argv[5]||'shot')+'.png', clip:{x:0,y:0,width:1280,height:720}, timeout: 300000 }); console.log('shot ms', Date.now()-t0);
  await browser.close();
})();
