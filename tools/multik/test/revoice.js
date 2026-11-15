// Нейроголос в сборке приложения и плашка «Серии, собранные без нейроголоса» (сборка 58).
// Сборки 55–57 вышли из папки на Маке без voice/ и ort/ — рассказчик, Барсик и медведи молча читали голосом iPhone.
//   node tools/multik/test/revoice.js [--voice=папка с voice/ и ort/]
// Два прохода: без файлов голоса — красная плашка и вопрос перед сборкой; с файлами — список серий и «🎬 Пересобрать все».
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http');
const args = process.argv.slice(2), opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel');
const VDIR = [opt('voice'), ROOT, '/home/claude/mv', '/home/claude/voice'].filter(Boolean).find(d => fs.existsSync(path.join(d, 'voice', 'xenia', 'tts.json')) && fs.existsSync(path.join(d, 'ort', 'ort.wasm.min.js')));
if (!VDIR) { console.log('✘ нет файлов нейроголоса (--voice=папка)'); process.exit(2); }
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json' };
const serve = withVoice => http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]), v = /^\/(voice|ort)\//.test(u); if (v && !withVoice) { r.writeHead(404); r.end(); return; }
  const f = v ? path.join(VDIR, u) : path.join(ROOT, u); fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
let bad = 0; const ok = (c, m) => { console.log((c ? '✔ ' : '✘ ') + m); if (!c) bad++; };
const EPS = [ // серия, когда собрана, voiceFb → должна ли быть в плашке
  { episode: 1, built: '2026-11-10T12:00:00Z', want: false, title: 'до сборок без голоса' },
  { episode: 2, built: '2026-11-12T15:30:00Z', want: true, title: 'сборка 56' },
  { episode: 3, built: '2026-11-13T09:00:00Z', want: true, title: 'сборка 57' },
  { episode: 4, built: '2026-11-15T10:00:00Z', voiceFb: 0, want: false, title: 'сборка 58, всё нейроголосом' },
  { episode: 5, built: '2026-11-15T11:00:00Z', voiceFb: 4, want: true, title: 'сборка 58, 4 реплики голосом iPhone' },
  { episode: 6, want: false, title: 'не собрана' },
  { episode: 7, built: '2026-11-14T10:00:00Z', voiceOk: 1, want: false, title: 'скрыта кнопкой «в порядке»' },
];
async function run(b, withVoice) {
  const srv = serve(withVoice); await new Promise(r => srv.listen(0, r));
  const p = await (await b.newContext({ viewport: { width: 430, height: 900 } })).newPage();
  const st = { lib: null }, dialogs = []; p.on('pageerror', e => { console.log('ERR', e.message); bad++; }); p.on('dialog', d => { dialogs.push(d.message()); d.type() === 'confirm' ? d.dismiss() : d.accept(); });
  await p.exposeFunction('__native', async m => { switch (m.cmd) { case 'load': return st.lib; case 'save': st.lib = m.json; return true; case 'thermal': return 0; case 'parked': return false; default: return null; } });
  await p.addInitScript(() => { window.webkit = { messageHandlers: { multik: { postMessage: m => window.__native(m) } } }; });
  await p.goto(`http://localhost:${srv.address().port}/multik.html`); await p.waitForFunction(() => typeof Lib !== 'undefined' && Lib.data && typeof App !== 'undefined' && document.querySelector('.tabs'), null, { timeout: 60000 });
  await p.evaluate(async EPS => { Lib.data.projects = [{ series: 'Кот Барсик', episodes: EPS.map(x => Object.assign({ status: x.built ? 'built' : 'draft', video: x.built ? 'video/' + x.episode + '.mp4' : undefined, script: { scenes: [] } }, x, { want: undefined })) }];
    window.__loops = 0; Build.loop = async () => { window.__loops++; }; App.tab = 'series'; App.render(); }, EPS);
  await p.waitForFunction(() => VoiceCheck.st !== null, null, { timeout: 20000 }); await p.waitForTimeout(300);
  const r = await p.evaluate(() => ({ st: VoiceCheck.st, red: !!document.getElementById('novoice'), card: !!document.getElementById('revoice'), text: (document.getElementById('revoice') || {}).innerText || '',
    tags: [...document.querySelectorAll('.ep')].map(d => /без нейроголоса/.test(d.innerText)), list: Revoice.list().map(x => x.e.episode) }));
  return { p, srv, r, dialogs, st };
}
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  // 1) сборка без файлов голоса (как 55–57)
  let { p, srv, r, dialogs } = await run(b, false);
  ok(r.st === false && r.red && !r.card, 'нет файлов голоса — красная плашка «В этой сборке приложения нет нейроголоса», списка серий нет');
  await p.evaluate(async () => { const P = Lib.data.projects[0]; await Build.run(P, P.episodes[5]); });
  ok(dialogs.some(d => /голосом iPhone/.test(d) && /Всё равно собрать/.test(d)) && (await p.evaluate(() => Build.jobs().length)) === 0 && (await p.evaluate(() => window.__loops)) === 0, '«Собрать видео» сначала спрашивает; «Отмена» — серия не встаёт в очередь');
  srv.close();
  // 2) голос на месте (сборка 58)
  ({ p, srv, r, dialogs } = await run(b, true));
  const want = EPS.filter(x => x.want).map(x => x.episode);
  ok(r.st === true && !r.red && r.card, 'файлы голоса на месте — красной плашки нет, есть «Серии, собранные без нейроголоса»');
  ok(JSON.stringify(r.list) === JSON.stringify(want), `в списке серии ${r.list.join(', ')} (ждали ${want.join(', ')}): до 12.11 и собранные 58-й сборкой нейроголосом — не трогаем`);
  ok(JSON.stringify(r.tags) === JSON.stringify(EPS.map(x => x.want)), 'у этих серий пометка «без нейроголоса» в списке серий');
  ok(/Пересобрать все \(3\)/.test(r.text) && /12\.11/.test(r.text) && /13\.11/.test(r.text), 'кнопка «🎬 Пересобрать все (3)», у серий — день сборки');
  if (process.env.SHOT) await p.locator('#revoice').screenshot({ path: process.env.SHOT });
  await p.click('#revoice [data-rv="all"]'); await p.waitForTimeout(300);
  const q = await p.evaluate(() => ({ q: Build.jobs().map(j => j.episode), loops: window.__loops, saved: JSON.parse(window.__lastSave || 'null') }));
  ok(JSON.stringify(q.q) === JSON.stringify(want) && q.loops === 1, `по кнопке все три встали в очередь (${q.q.join(', ')}) и сборка пошла`);
  await p.click('#revoice [data-rv="all"]').catch(() => {}); await p.waitForTimeout(200);
  ok((await p.evaluate(() => Build.jobs().length)) === want.length, 'повторное нажатие не задваивает очередь');
  // сборка 58 закончила серию 2 нейроголосом → пропадает из списка
  const after = await p.evaluate(() => { const e = Lib.data.projects[0].episodes[1]; e.voiceFb = 0; return Revoice.list().map(x => x.e.episode); });
  ok(JSON.stringify(after) === JSON.stringify([3, 5]), 'пересобранная нейроголосом серия уходит из списка');
  // «Эти в порядке — скрыть»: confirm → да
  await p.evaluate(() => { window.confirm = () => true; Build.jobs().length = 0; App.render(true); }); await p.click('#revoice [data-rv="ok"]'); await p.waitForTimeout(200);
  ok(!(await p.evaluate(() => !!document.getElementById('revoice'))) && (await p.evaluate(() => Revoice.list().length)) === 0, '«Эти в порядке — скрыть» убирает плашку');
  srv.close(); await b.close(); console.log(bad ? `✘ ошибок: ${bad}` : '✔ всё в порядке'); process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
