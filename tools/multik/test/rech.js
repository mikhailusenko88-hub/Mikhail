// БАРС-озвучка: проверка произношения без телефона — обязательна перед установкой.
// Гоняет проверочные фразы (rech-homo.json: фраза → каким должно быть ударное слово) через тот же путь, что и в телефоне
// (словарь пользователя → грамматика → омографы → модель ударений), и печатает, где ударение не то.
//   node tools/multik/test/rech.js [--voice=папка с voice/ и ort/ (ветка multik-voice)] [--old — как было до БАРС-озвучки] [--strict — строго по словарю]
// Третье значение во фразе — вариант по словарю там, где словарь расходится с живой речью («возле две́ри» по словарю, «возле двери́» в жизни).
// По умолчанию ждём «как в жизни» (так утвердил Михаил 10.11.2026), с --strict (BARSRech.strict = true) — вариант по словарю.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http');
const args = process.argv.slice(2), opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel');
const VDIR = [opt('voice'), ROOT, '/home/claude/mv'].filter(Boolean).find(d => fs.existsSync(path.join(d, 'voice', 'homo.json')) && fs.existsSync(path.join(d, 'ort', 'ort.wasm.min.js')));
if (!VDIR) { console.log('✘ нет файлов голоса: git clone -b multik-voice https://github.com/mikhailusenko88-hub/Mikhail <папка> и --voice=<папка>'); process.exit(2); }
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.wasm': 'application/wasm' };
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]); const f = /^\/(voice|ort)\//.test(u) ? path.join(VDIR, u) : path.join(ROOT, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
(async () => { await new Promise(r => srv.listen(0, r)); const b = await chromium.launch(); const p = await b.newPage(); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto(`http://localhost:${srv.address().port}/voice.html`);
  const T = JSON.parse(fs.readFileSync(path.join(__dirname, 'rech-homo.json'), 'utf8'));
  const strict = args.includes('--strict');
  const R = await p.evaluate(async ({ T, old, strict }) => { if (old) { window.BARSRech = null; window.__HOMO_SENT = false; } else if (strict) window.BARSRech.strict = true; await MKVoice.load(''); const out = []; for (const [s] of T) out.push(await MKVoice.marks(s, null)); return out; }, { T, old: args.includes('--old'), strict });
  await b.close(); srv.close(); let bad = 0;
  T.forEach(([s, live, dict], i) => { const exp = strict && dict ? dict : live; if (!R[i].toLowerCase().includes(exp)) { bad++; console.log(`✘ ${R[i]}   — нужно: ${exp}`); } });
  console.log(`${bad ? '✘' : '✔'} ударения: верно ${T.length - bad} из ${T.length}${args.includes('--old') ? ' (как было)' : strict ? ' (строго по словарю)' : ''}`); process.exit(bad && !args.includes('--old') ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
