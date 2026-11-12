// «Подписка на канал»: настройки на настоящей странице multik.html и строка со ссылкой в «Тексте для YouTube / Rutube»; кадры кнопки — render.js.
//   node tools/multik/test/sub.js
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http');
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json' };
const srv = http.createServer((q, r) => { const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
let bad = 0; const ok = (c, m) => { console.log((c ? '✔ ' : '✘ ') + m); if (!c) bad++; };
(async () => {
  await new Promise(r => srv.listen(0, r)); const port = srv.address().port;
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] }); const p = await (await b.newContext({ viewport: { width: 430, height: 900 } })).newPage();
  const st = { lib: null, copied: [] }; p.on('pageerror', e => { console.log('ERR', e.message); bad++; }); p.on('dialog', d => d.accept());
  await p.exposeFunction('__native', async m => { switch (m.cmd) { case 'load': return st.lib; case 'save': st.lib = m.json; return true; case 'copy': st.copied.push(m.text); return true; case 'thermal': return 0; case 'parked': return false; default: return null; } });
  await p.addInitScript(() => { window.webkit = { messageHandlers: { multik: { postMessage: m => window.__native(m) } } }; });
  await p.goto(`http://localhost:${port}/multik.html`); await p.waitForFunction(() => typeof Lib !== 'undefined' && Lib.data && typeof App !== 'undefined' && document.querySelector('.tabs'), null, { timeout: 60000 });
  await p.evaluate(() => { App.tab = 'set'; App.render(); }); if (process.env.SHOT) await p.locator('.card', { has: p.locator('#subOn') }).screenshot({ path: process.env.SHOT });   // SHOT=файл.png — снимок карточки
  const ui = await p.evaluate(() => { const $ = id => document.getElementById(id); return { on: $('subOn').checked, badge: $('subBadge').checked, who: $('subWho').value, line: $('subLine').value, yt: $('subYt').value, rt: $('subRt').value, desc: $('subDesc').checked }; });
  ok(ui.on && ui.badge && ui.desc && ui.who === 'hero', 'по умолчанию всё включено, говорит главный герой');
  ok(/подписаться на канал/.test(ui.line) && /@Cartoon_Friend3/.test(ui.yt) && /rutube\.ru\/channel\//.test(ui.rt), 'фраза и ссылки по умолчанию');
  await p.selectOption('#subWho', 'narrator'); await p.fill('#subLine', 'Подпишись на канал!'); await p.dispatchEvent('#subLine', 'change'); await p.uncheck('#subBadge');
  let s = await p.evaluate(() => Lib.data.settings.sub); ok(s.who === 'narrator' && s.line === 'Подпишись на канал!' && s.badge === false, 'настройки запоминаются: ' + JSON.stringify(s));
  const lines = await p.evaluate(() => { const ep = { episode: 1, title: 'Т', scenes: [{ location: 'л', cast: [{ who: 'к' }], steps: [{ who: 'к', say: 'Привет!' }] }] };
    const lib = { characters: { к: { spec: { id: 'к', name: 'Кот', kind: 'cat', voice: { base: 'female', pitch: 1, rate: .5 } } } }, locations: {}, settings: Lib.data.settings };
    const L = MK.collectLines(ep, lib), sl = L[L.length - 1], tl = MK.compile(ep, lib, {}); return { n: L.length, who: sl && sl.who, text: sl && sl.subText, end: tl.segs[tl.segs.length - 1], marks: tl.sub && tl.sub.marks }; });
  ok(lines.who === 'Р' && lines.text === 'Подпишись на канал!' && lines.end.say && lines.end.say.who === 'Р', 'фразу говорит рассказчик, она в озвучке и на последней заставке');
  ok(lines.end.tap == null, 'кнопка в кадре выключена — лапки нет');
  await p.fill('#subLine', ''); await p.dispatchEvent('#subLine', 'change'); s = await p.evaluate(() => Lib.data.settings.sub); ok(s.line === undefined && (await p.inputValue('#subLine')) === await p.evaluate(() => MK.SUB_LINE), 'пустая фраза — снова фраза по умолчанию');
  await p.evaluate(() => { Lib.data.projects = [{ series: 'Кот Барсик', episodes: [{ episode: 3, title: 'Грибы', status: 'draft', script: { scenes: [], youtube: { title: 'Кот Барсик — Серия 3', description: 'Описание.', tags: ['мультик'] } } }] }]; App.tab = 'series'; App.render(); });
  for (const a of ['yt', 'rt']) await p.locator(`[data-a="${a}"]`).first().click();
  console.log(st.copied.map(t => '---\n' + t).join('\n'));
  ok(st.copied.length === 2 && /youtube\.com\/@Cartoon_Friend3\?sub_confirmation=1/.test(st.copied[0]) && /rutube\.ru\/channel\/82826859/.test(st.copied[1]) && !/youtube/.test(st.copied[1]), 'в тексте для YouTube — ссылка с окном подписки, для Rutube — ссылка на канал Rutube');
  await p.evaluate(() => { Lib.data.settings.sub.on = false; });
  const off = await p.evaluate(() => { const ep = { episode: 1, scenes: [{ location: 'л', cast: [{ who: 'к' }], steps: [{ who: 'к', say: 'Привет!' }] }] }; const lib = { characters: { к: { spec: { id: 'к', name: 'Кот', kind: 'cat' } } }, locations: {}, settings: Lib.data.settings };
    const tl = MK.compile(ep, lib, {}); return { sub: tl.sub, say: tl.segs[tl.segs.length - 1].say, n: MK.collectLines(ep, lib).length, desc: MK.subDescLine(lib, 'yt') }; });
  ok(!off.sub && !off.say && off.n === 1 && off.desc === '', 'выключено — ни кнопки, ни фразы, ни строки в описании');
  await b.close(); srv.close(); console.log(bad ? `✘ ошибок: ${bad}` : '✔ всё в порядке'); process.exit(bad ? 1 : 0);
})();
