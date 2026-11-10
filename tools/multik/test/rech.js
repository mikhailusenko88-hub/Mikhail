// БАРС-озвучка: проверка произношения без телефона — обязательна перед установкой.
// Гоняет проверочные фразы (rech-homo.json: фраза → каким должно быть ударное слово) тем же путём, что и в телефоне:
// реплика рассказчика → MK.lineFor (подготовка текста: «+», словарь ударений, словарь «ё») → страница голоса voice.html
// (словарь пользователя → грамматика → омографы → модель ударений) — и печатает, где ударение не то.
//   node tools/multik/test/rech.js [--voice=папка с voice/ и ort/ (ветка multik-voice)] [--old — как было до БАРС-озвучки] [--strict — строго по словарю]
//                                  [--raw — мимо подготовки текста, сразу в страницу голоса] [--yo — как будто в серии автор пишет «ё»]
// Третье значение во фразе — вариант по словарю там, где словарь расходится с живой речью («возле две́ри» по словарю, «возле двери́» в жизни).
// По умолчанию ждём «как в жизни» (так утвердил Михаил 10.11.2026), с --strict (BARSRech.strict = true) — вариант по словарю.
// Важно: проверять именно путём телефона. 10.11.2026 фразы шли мимо подготовки текста и давали 422 из 422, а в телефоне старое правило
// «все → всё» в MK.prepSpeech срабатывало раньше грамматики («всё вместе побежали») — было бы 413. Теперь подготовка текста уступает грамматике.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http');
const args = process.argv.slice(2), opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel');
const VDIR = [opt('voice'), ROOT, '/home/claude/mv'].filter(Boolean).find(d => fs.existsSync(path.join(d, 'voice', 'homo.json')) && fs.existsSync(path.join(d, 'ort', 'ort.wasm.min.js')));
if (!VDIR) { console.log('✘ нет файлов голоса: git clone -b multik-voice https://github.com/mikhailusenko88-hub/Mikhail <папка> и --voice=<папка>'); process.exit(2); }
const old = args.includes('--old'), strict = args.includes('--strict'), raw = args.includes('--raw'), epYo = args.includes('--yo');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.wasm': 'application/wasm' };
const ENG = ['multik-engine.js', 'multik-audio.js'].concat(old ? [] : ['multik-bars-rech.js', 'multik-bars-golos.js']);   // страница «Мультиков»: здесь реплика готовится к озвучке
const engHtml = '<html><head><meta charset="utf-8"></head><body>' + ENG.map(f => `<script src="/${f}"></script>`).join('') + '<script>window.ready=true;</script></body></html>';
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]); if (u === '/eng') { r.writeHead(200, { 'Content-Type': MIME['.html'] }); r.end(engHtml); return; }
  const f = /^\/(voice|ort)\//.test(u) ? path.join(VDIR, u) : path.join(ROOT, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
(async () => { await new Promise(r => srv.listen(0, r)); const port = srv.address().port, b = await chromium.launch();
  const T = JSON.parse(fs.readFileSync(path.join(__dirname, 'rech-homo.json'), 'utf8'));
  let M = T.map(t => t[0]);
  if (!raw) { const p1 = await b.newPage(); p1.on('pageerror', e => console.log('ERR', e.message)); await p1.goto(`http://localhost:${port}/eng`); await p1.waitForFunction(() => window.ready);
    M = await p1.evaluate(T => { const lib = { characters: {}, locations: {}, settings: {} }; return T.map(([s]) => { const ln = MK.lineFor({}, lib, 'Р', s, { say: s }, 0); return ln && ln.srv ? ln.srv.text : null; }); }, T);
    if (M.some(m => m === null)) { console.log('✘ рассказчик читает не нейроголосом — проверять нечего'); process.exit(2); } await p1.close(); }
  const p = await b.newPage(); p.on('pageerror', e => console.log('ERR', e.message)); await p.goto(`http://localhost:${port}/voice.html`);
  const R = await p.evaluate(async ({ M, S, old, strict, raw, epYo }) => { if (old) { window.BARSRech = null; window.__HOMO_SENT = false; } else if (strict) window.BARSRech.strict = true; await MKVoice.load(''); const out = [];
    for (let i = 0; i < M.length; i++) { const lex = old || raw ? (epYo && !old ? { yo: 1 } : null) : Object.assign({ yoLine: /ё/i.test(S[i]) ? 1 : 0 }, epYo ? { yo: 1 } : {});   // как SrvVoice.lex(ln) в multik.html
      out.push(await MKVoice.marks(M[i], lex)); } return out; }, { M, S: T.map(t => t[0]), old, strict, raw, epYo });
  await b.close(); srv.close(); let bad = 0;
  T.forEach(([s, live, dict], i) => { const exp = strict && dict ? dict : live; if (!R[i].toLowerCase().includes(exp)) { bad++; console.log(`✘ ${R[i]}   — нужно: ${exp}${M[i] !== s ? '   (после подготовки текста: ' + M[i] + ')' : ''}`); } });
  console.log(`${bad ? '✘' : '✔'} ударения${raw ? ' (мимо подготовки текста)' : ' (путём телефона)'}: верно ${T.length - bad} из ${T.length}${old ? ' (как было)' : strict ? ' (строго по словарю)' : ''}`); process.exit(bad && !old ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
