// БАРС-озвучка: проверка без телефона.
//   node tools/multik/test/golos.js lines [корень Resources/Mebel] — список реплик серии golos.txt (кто, ключ, чем озвучивается) в JSON
//   node tools/multik/test/golos.js same <корень старой версии>   — сравнить с прежней версией: реплики Барсика, Пика и рассказчика должны совпасть один в один
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http');
const HERE = __dirname, DEF = path.resolve(HERE, '../../../Resources/Mebel');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json' };
async function lines(root) {
  const scripts = ['multik-engine.js', 'multik-audio.js', 'multik-laugh.js', 'multik-bars-rech.js', 'multik-bars-golos.js', 'multik-maker.js', 'multik-script.js'].filter(f => fs.existsSync(path.join(root, f)));
  const html = '<html><head><meta charset="utf-8"></head><body>' + scripts.map(f => `<script src="/${f}"></script>`).join('') + '<script>window.ready=true;</script></body></html>';
  const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]); if (u === '/') { r.writeHead(200, { 'Content-Type': MIME['.html'] }); r.end(html); return; }
    fs.readFile(path.join(root, u), (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(u)] || 'application/octet-stream' }); r.end(d); }); });
  await new Promise(r => srv.listen(0, r)); const b = await chromium.launch(); const p = await b.newPage(); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto(`http://localhost:${srv.address().port}/`); await p.waitForFunction(() => window.ready);
  const res = await p.evaluate(txt => { const r = MKScript.parse(txt, { characters: {}, locations: {} }); const ep = r.episodes[0]; const lib = { characters: {}, locations: {}, settings: {} }; const v = MK.validate(ep, lib);
    for (const c of v.newChars) lib.characters[c.id] = { spec: c, code: c._code }; for (const l of v.newLocs) lib.locations[l.id] = { spec: l, code: l._code };
    const name = w => w === 'Р' ? 'рассказчик' : w === '?' ? '?' : (lib.characters[w] && lib.characters[w].spec.name) || w;
    return MK.collectLines(ep, lib).map(l => ({ who: name(l.who), key: l.key, text: l.text, synth: l.synth || '', short: !!l.short, fx: l.fx && l.fx.id, voice: l.voice, srv: l.srv || null, src: l.src || '' })); }, fs.readFileSync(path.join(HERE, 'golos.txt'), 'utf8'));
  await b.close(); srv.close(); return res; }
(async () => { const mode = process.argv[2] || 'lines';
  if (mode === 'lines') { console.log(JSON.stringify(await lines(process.argv[3] || DEF), null, 1)); return; }
  if (mode === 'same') { const A = await lines(process.argv[3]), B = await lines(DEF); let bad = 0, changed = 0;
    console.log(`реплик: было ${A.length}, стало ${B.length}`);
    for (let i = 0; i < Math.max(A.length, B.length); i++) { const a = A[i], b = B[i]; if (!a || !b) { bad++; console.log('✘ разное число реплик', i); continue; }
      const same = JSON.stringify(a) === JSON.stringify(b), bars = b.srv && b.srv.bars;
      if (same) { console.log(`= ${b.who}: ${b.text.slice(0, 46)}`); continue; }
      if (bars) { changed++; console.log(`~ ${b.who}: ${b.text.slice(0, 40)} → БАРС ${JSON.stringify(b.srv.bars)}`); continue; }   // смех, «Ура-а-а», «Мяу» — намеренно по-новому
      bad++; console.log(`✘ ${b.who}: «${b.text}» изменилась без причины\n   было : ${JSON.stringify(a)}\n   стало: ${JSON.stringify(b)}`); }
    console.log(bad ? `✘ НЕ СОВПАЛО: ${bad}` : `✔ обычные реплики совпали один в один; по-новому (БАРС): ${changed}`); process.exit(bad ? 1 : 0); }
})().catch(e => { console.error(e); process.exit(1); });
