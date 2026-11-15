// Обложка (🖼) и Shorts (📱) из готовой серии — без телефона.  node tools/multik/test/oblozhka.js сценарий.txt [--out=папка] [--hq]
// Обложка: 1280×720 JPG ≤ 2 МБ с надписями и без; Shorts: кусок 20–30 с, вертикальные кадры 1080×1920 (здесь — 2 кадра/с, чтобы быстро).
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http');
const args = process.argv.slice(2), opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel'), OUT = opt('out') || '/tmp/oblozhka', HQ = args.includes('--hq'); fs.mkdirSync(OUT, { recursive: true });
const scn = args.find(a => !a.startsWith('--')) || path.join(__dirname, 'smoke.txt');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.wasm': 'application/wasm' };
const srv = http.createServer((q, r) => { const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
let bad = 0; const ok = (c, m) => { console.log((c ? '✔ ' : '✘ ') + m); if (!c) bad++; };
(async () => { await new Promise(r => srv.listen(0, r));
  const b = await chromium.launch({ timeout: 180000, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 430, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => { console.log('  окно:', d.message().slice(0, 200)); d.accept(); });
  const files = {}; await p.exposeFunction('__save', (name, b64) => { const f = path.join(OUT, name); fs.writeFileSync(f, Buffer.from(b64, 'base64')); files[name] = fs.statSync(f).size; return true; });
  await p.goto(`http://localhost:${srv.address().port}/multik.html`); await p.waitForFunction(() => window.MK3D && MK3D.ready && typeof Lib !== 'undefined' && Lib.data, null, { timeout: 120000 });
  const info = await p.evaluate(async ({ txt, hq }) => { MK3D.setQuality(hq ? 'hq' : 'std'); Lib.data.settings.quality = hq ? 'hq' : 'std';
    const r = MKScript.parse(txt, Lib.data); for (const c of r.newChars) Lib.data.characters[c.id] = { spec: c }; for (const l of r.newLocs) Lib.data.locations[l.id] = { spec: l };
    const ep = r.episodes[0]; const P = { series: ep.series, episodes: [{ episode: ep.episode, title: ep.title, script: ep, status: 'built', video: 'video/' + ep.series + ' - ' + ep.episode + '.mp4', made: { app: '59', intro: 'after', open: 'new' }, aud2: {} }] }; Lib.data.projects = [P];
    window.__frames = []; window.__share = []; let n = 0;
    Object.assign(Mock, { writeFile: a => { window.__save(a.path.split('/').pop(), a.d); return { path: a.path }; }, share: a => { window.__share.push(a.paths || [a.path]); return true; }, keepAwake: () => true,
      videoBegin: a => { window.__vb = a; n = 0; return { ok: true, frames: 0 }; }, videoFrame: a => { n++; if (a.i === 0 || a.i === window.__mid) window.__save('shorts_' + a.i + '.jpg', a.d); return 1; }, videoEnd: a => { window.__ve = a; return { path: 'video/x - Shorts.mp4', n }; } });
    return { errors: r.errors.length, ep: ep.episode, title: ep.title, main: ep.main }; }, { txt: fs.readFileSync(scn, 'utf8'), hq: HQ });
  console.log('серия', info.ep, info.title, '· главное:', info.main || '—', '· ошибок разбора', info.errors);
  const t0 = Date.now(); await p.evaluate(async () => { const P = Lib.data.projects[0]; await Cover.make(P, P.episodes[0], null); }); console.log('обложка за', ((Date.now() - t0) / 1000).toFixed(0), 'с');
  const cov = Object.keys(files).filter(f => /обложка/.test(f));
  ok(cov.length === 2 && cov.every(f => files[f] > 30000 && files[f] <= 2e6), `обложка: ${cov.map(f => f + ' ' + (files[f] / 1024).toFixed(0) + ' КБ').join(', ')}`);
  ok((await p.evaluate(() => (window.__share[0] || []).length)) === 2, 'обложка уходит в «Поделиться» двумя файлами');
  const t1 = Date.now(); await p.evaluate(async fps => { Shorts.FPS = fps; window.__mid = Math.round(12 * fps); const P = Lib.data.projects[0]; await Shorts.make(P, P.episodes[0], null); }, +(process.env.SFPS || 2));   // SFPS=0.4 — 10 кадров (для «как в кино»)
  const sh = await p.evaluate(() => ({ vb: window.__vb, ve: window.__ve, path: Lib.data.projects[0].episodes[0].shorts })); console.log('Shorts за', ((Date.now() - t1) / 1000).toFixed(0), 'с');
  ok(sh.vb && sh.vb.w === 1080 && sh.vb.h === 1920 && sh.vb.dir === 'tmp/shorts' && sh.vb.audioSrc && sh.vb.audioFrom >= 0, `Shorts: ${sh.vb ? sh.vb.w + '×' + sh.vb.h : '—'}, звук из серии с ${sh.vb ? sh.vb.audioFrom.toFixed(1) : '?'} с, куски в tmp/shorts`);
  ok(sh.ve && /Shorts из серии/.test(sh.ve.comment || '') && !!sh.path, `Shorts записан: ${sh.ve ? sh.ve.comment : '—'}`);
  ok(!errs.length, 'без ошибок страницы' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
  console.log('файлы:', Object.keys(files).map(f => path.join(OUT, f)).join('\n       '));
  await b.close(); srv.close(); process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
