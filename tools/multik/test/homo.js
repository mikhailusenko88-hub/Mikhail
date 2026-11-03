// Омографы для голосов iPhone: node tools/multik/test/homo.js — сервер над Resources/Mebel, страница с движком и нейроголосом,
// MKVoice.homoMarks(фраза) → где поставлены «+». Нужны voice/homo.json (+homo_emb.q8, homo.onnx) и ort/ (ветка multik-voice).
const { chromium } = require('playwright'); const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel');
const MIME = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.wasm': 'application/wasm', '.html': 'text/html' };
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]), f = path.join(ROOT, u === '/' ? 'homo-test.html' : u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
const PAGE = `<html><head><meta charset="utf-8"></head><body><script src="multik-engine.js"></script><script src="multik-audio.js"></script><script src="multik-voice.js"></script><script>window.ready=true;</script></body></html>`;
const TESTS = [
  'Вдали на холме стоял старый замок короля.', 'Барсик повесил на дверь большой замок и закрыл его ключом.', 'Мама купила муку для пирога.',
  'Это была настоящая мука — ждать до вечера.', 'Сколько стоит этот мяч?', 'Пик стоит у окна и ждёт.', 'Большая часть торта уже съедена.',
  'У нас большая кухня.', 'Рон уже пришёл домой.', 'Ирис расцвёл у крыльца.', 'Белки прыгают по веткам.', 'Пик бежит бегом к дому.',
  'Я сегодня дома.', 'З+амок на двери, — сказал Рон.', 'Привет! Как дела?',
];
(async () => {
  fs.writeFileSync(path.join(ROOT, 'homo-test.html'), PAGE);
  await new Promise(res => srv.listen(0, res)); const port = srv.address().port;
  const b = await chromium.launch(); const p = await b.newPage(); p.on('pageerror', e => console.log('ERR', e.message)); p.on('console', m => { const t = m.text(); if (!/^Failed to load/.test(t)) console.log('C', t.slice(0, 160)); });
  await p.goto(`http://localhost:${port}/`); await p.waitForFunction(() => window.ready);
  const t0 = Date.now();
  const res = await p.evaluate(async (tests) => { const out = []; for (const t of tests) { const t1 = performance.now(); const m = await MKVoice.homoMarks(t, {}); out.push([t, m, Math.round(performance.now() - t1), MKHomo.ready ? 'bert' : 'dict']); } return out; }, TESTS);
  for (const [t, m, ms, how] of res) console.log((m === t ? '   ' : ' + ') + m + '   [' + ms + ' мс, ' + how + ']');
  // как это уйдёт в iPhone: текст + IPA для отмеченных слов
  const ipa = await p.evaluate(async (tests) => tests.map(t => { const ps = MK.prepSpeech(t, {}, 'ipa'); return [ps.text, ps.ipa.map(x => ps.text.substr(x[0], x[1]) + '=' + x[2]).join(' ')]; }), res.slice(0, 3).map(r => r[1]));
  for (const [t, i] of ipa) console.log('IPA:', t, '→', i);
  console.log('всего', Date.now() - t0, 'мс');
  await b.close(); srv.close(); fs.unlinkSync(path.join(ROOT, 'homo-test.html'));
})();
