// Выгрузка кадров плана из движка «Мультиков» для Blender.
//   ENG=<клон mebel-3d> node export.js сценарий.txt папка t0 fps n [--w=1280]
// В папке: f_<NNN>.json + f_<NNN>.bin (геометрия кадра), f_<NNN>_eng.png (кадр движка — для глаз), tex/*.png (текстуры комнаты).
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const ENG = process.env.ENG; const a = process.argv.slice(2), pos = a.filter(x => !x.startsWith('--')), opt = (k, d) => { const x = a.find(y => y.startsWith('--' + k + '=')); return x ? x.split('=')[1] : d; };
const [SCN, OUT, T0, FPS, NF] = [pos[0], pos[1], +pos[2], +pos[3] || 25, +pos[4] || 1]; const FROM = +opt('from', 0), W = +opt('w', 1280), H = Math.round(W * 9 / 16);
const t00 = Date.now(), el = () => ((Date.now() - t00) / 1000).toFixed(0) + 'с';
(async () => {
  fs.mkdirSync(path.join(OUT, 'tex'), { recursive: true });
  const b = await chromium.launch({ executablePath: process.env.CHROME || undefined, timeout: 180000, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files', '--js-flags=--max-old-space-size=6000'] });
  const p = await b.newPage({ viewport: { width: 400, height: 300 } });
  p.on('pageerror', e => console.log('ERR', e.message)); p.on('console', m => { const s = m.text(); if (/^CAP|error/i.test(s)) console.log(s.slice(0, 300)); });
  await p.exposeFunction('__save', (name, b64) => { fs.appendFileSync(path.join(OUT, name), Buffer.from(b64, 'base64')); return true; });
  await p.goto('file://' + path.join(ENG, 'tools/multik/test/frame.html') + '#hq'); await p.waitForFunction(() => window.ready, null, { timeout: 1200000 });
  console.log('страница готова', el(), await p.evaluate(() => [window.h6Ok, window.barsikOk]));
  await p.addScriptTag({ path: path.join(__dirname, 'cap.js') });
  const info = await p.evaluate(t => setupText(t), fs.readFileSync(SCN, 'utf8')); console.log('серия', JSON.stringify(info).slice(0, 200));
  await p.evaluate(([w, h]) => { const c = document.getElementById('c'); c.width = w; c.height = h; }, [W, H]);
  for (let f = FROM; f < FROM + NF; f++) {
    const t = T0 + f / FPS, tag = 'f_' + String(f).padStart(3, '0');
    await p.evaluate(t => { frame(t - 1 / 25); frame(t); }, t);   // два кадра подряд: пружинки шерсти и сглаживание движений как в серии
    await p.locator('#c').screenshot({ path: path.join(OUT, tag + '_eng.png'), timeout: 600000 });
    for (const ext of ['.bin', '.json']) try { fs.unlinkSync(path.join(OUT, tag + ext)); } catch (e) {}
    const man = await p.evaluate(async (tag) => {
      const r = CAP.capture(); const u8 = new Uint8Array(r.size); let o = 0; for (const bb of r.bins) { u8.set(new Uint8Array(bb), o); o += bb.byteLength; }
      const CH = 8 << 20; for (let i = 0; i < u8.length; i += CH) { const s = u8.subarray(i, Math.min(u8.length, i + CH)); let bin = ''; for (let j = 0; j < s.length; j += 32768) bin += String.fromCharCode.apply(null, s.subarray(j, j + 32768)); await window.__save(tag + '.bin', btoa(bin)); }
      const tex = []; for (const ob of r.objs) if (ob.mat) for (const k of ['map', 'emap', 'amap']) { const tx = ob.mat[k]; if (tx && tx.url) { tex.push([tx.id, tx.url]); delete tx.url; } else if (tx) delete tx.url; }
      delete r.bins; return { r, tex };
    }, tag);
    for (const [id, url] of man.tex) fs.writeFileSync(path.join(OUT, 'tex', id + '.png'), Buffer.from(url.split(',')[1], 'base64'));
    man.r.t = t; man.r.frame = f; man.r.W = W; man.r.H = H;
    fs.writeFileSync(path.join(OUT, tag + '.json'), JSON.stringify(man.r));
    console.log(tag, 't=' + t.toFixed(3), 'объектов', man.r.objs.length, (man.r.size / 1e6).toFixed(1) + ' МБ', JSON.stringify(man.r.stat), el());
  }
  await b.close();
})().catch(e => { console.log('СБОЙ', e && e.stack || e); process.exit(2); });
