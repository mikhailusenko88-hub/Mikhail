const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const logs=[]; page.on('pageerror', e => logs.push('ERR: '+e.message));
  await page.goto('http://localhost:8767/index.html?still=1&samples=0&w=640', { waitUntil: 'load' });
  await page.waitForFunction(() => document.getElementById('load').style.display === 'none' || document.getElementById('load').textContent.startsWith('Ошибка'), null, { timeout: 180000 });
  const setup=process.argv[2]||''; const n=+process.argv[3]||8; const dt=+process.argv[4]||0.12; const name=process.argv[5]||'seq';
  await page.evaluate((setup)=>{ eval(setup); }, setup);
  for(let i=0;i<n;i++){ await page.evaluate((t)=>window.renderOnce(t), 3.0+i*dt); await page.screenshot({ path: `${name}_${String(i).padStart(2,'0')}.png`, clip:{x:0,y:0,width:1280,height:720}, timeout: 300000 }); }
  console.log(logs.join('\n')); await browser.close();
})();
