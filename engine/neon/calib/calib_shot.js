// node calib_shot.js <cal 0/1> <outdir> f1 f2 ...  → <outdir>/p_<f>.png (кадр проектора без зерна) и <outdir>/id_<f>.bin (карта диодов, RGBA, снизу вверх)
const { chromium } = require('playwright'); const fs=require('fs');
(async () => {
  const cal=process.argv[2]==='1', out=process.argv[3]; const frames=process.argv.slice(4).map(Number); fs.mkdirSync(out,{recursive:true});
  const browser = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const logs=[]; page.on('pageerror', e => logs.push('ERR: '+e.message)); page.on('console', m => { if(m.type()==='error') logs.push(m.text()); });
  await page.goto('http://localhost:8766/index.html?still=1&samples=0&w=1280', { waitUntil: 'load' });
  await page.waitForFunction(() => document.getElementById('load').style.display === 'none' || document.getElementById('load').textContent.startsWith('Ошибка'), null, { timeout: 180000 });
  await page.evaluate((cal)=>{ st.grain=false; st.cal=cal; st.idMode=false; }, cal);
  for(const f of frames){
    await page.evaluate((f)=>{ st.idMode=false; window.renderOnce(f); }, f);
    await page.screenshot({ path: `${out}/p_${f}.png`, clip:{x:0,y:0,width:1280,height:720}, timeout: 300000 });
    if(!cal){ const b64=await page.evaluate((f)=>{ st.idMode=true; window.renderOnce(f); st.idMode=false; const px=G.idPixels; let s=''; const CH=0x8000; for(let i=0;i<px.length;i+=CH) s+=String.fromCharCode.apply(null,px.subarray(i,i+CH)); return btoa(s); }, f);
      fs.writeFileSync(`${out}/id_${f}.bin`, Buffer.from(b64,'base64')); }
    console.log('frame',f,'ok');
  }
  console.log(logs.join('\n')); await browser.close();
})();
