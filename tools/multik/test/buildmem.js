// Проверка СБОРКИ видео целиком, как в телефоне (без Xcode): настоящая страница multik.html, мост iPhone подменён здесь,
// нейроголос — в отдельном процессе (как MultikVoiceHost), «запись видео» только считает кадры.
// Смотрит главное для памяти: звук серии уходит в телефон → страница перезапускается → кадры рисуются на свежей странице
// БЕЗ повторной озвучки (длительности реплик сохранены) → видео дописано до конца.
//   node tools/multik/test/build.run.js [сценарий.txt] [--voice=папка с voice/ и ort/] [--hq] [--fps=2]
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), http = require('http'); const { execSync } = require('child_process');
const args = process.argv.slice(2), opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel');
const scn = path.resolve(args.find(a => !a.startsWith('--')) || path.join(__dirname, 'smoke.txt'));
const VDIR = [opt('voice'), ROOT, '/home/claude/mv', '/home/claude/voice'].filter(Boolean).find(d => fs.existsSync(path.join(d, 'voice', 'voc.onnx')) && fs.existsSync(path.join(d, 'ort', 'ort.wasm.min.js')));
if (!VDIR) { console.log('✘ нет файлов нейроголоса (--voice=папка)'); process.exit(2); }
const FPS = +(opt('fps') || 2), HQ = args.includes('--hq');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.wasm': 'application/wasm' };
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]); const f = /^\/(voice|ort)\//.test(u) ? path.join(VDIR, u) : path.join(ROOT, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
const procs = () => { try { return execSync("ps -eo pid,rss,args | grep -- '--type=renderer' | grep -v grep").toString().trim().split('\n').map(l => { const a = l.trim().split(/\s+/); return { pid: +a[0], mb: +a[1] / 1024 | 0 }; }); } catch (e) { return []; } };
(async () => {
  await new Promise(r => srv.listen(0, r)); const port = srv.address().port;
  const b = await chromium.launch({ timeout: 180000, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport: { width: 430, height: 900 } }); const p = await ctx.newPage();
  // «телефон»: библиотека, звук, видео, голос
  const st = { lib: null, audioBytes: 0, audioChunks: 0, frames: 0, began: 0, ended: null, voice: 0, voiceAfterReload: 0, loads: 0, stages: [], unload: 0 };
  let vctx = null, vp = null;
  const ENC = `const y=await MKVoice.speak(a.text,a.opts);const n=y.length,b=new Uint8Array(n*2);for(let i=0;i<n;i++){let v=Math.max(-1,Math.min(1,y[i]));v=Math.round(v<0?v*32768:v*32767);b[2*i]=v&255;b[2*i+1]=(v>>8)&255;}let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return{pcm:btoa(s),n:n,last:MKVoice.lastText||''};`;
  await p.exposeFunction('__native', async m => {
    switch (m.cmd) {
      case 'load': return st.lib; case 'save': st.lib = m.json; return true;
      case 'stage': if (m.text && st.stages[st.stages.length - 1] !== m.text) st.stages.push(m.text); return true;
      case 'crashInfo': return null; case 'keepAwake': case 'buildDone': case 'videoCancel': return true; case 'parked': return false; case 'thermal': return 0;
      case 'voiceSpeak': st.voice++; if (st.loads > 1) st.voiceAfterReload++;
        try { if (!vp) { vctx = await b.newContext(); vp = await vctx.newPage(); await vp.goto(`http://localhost:${port}/voice.html`); }
          return await vp.evaluate(new Function('a', 'return (async()=>{' + ENC + '})()'), m); } catch (e) { return { error: String(e && e.message || e) }; }
      case 'voiceUnload': st.unload++; if (vctx) { const c = vctx; vctx = null; vp = null; await c.close(); } return true;
      case 'audioChunk': if (m.first) st.audioBytes = 0; st.audioChunks++; st.audioBytes += Math.floor((m.d || '').length * 3 / 4); return true;
      case 'videoBegin': st.began++; return { ok: true, frames: st.frames };
      case 'videoFrame': st.frames++; return 1;
      case 'videoEnd': st.ended = { frames: st.frames }; return { path: '/tmp/test.mp4' };
      case 'tts': case 'resolveVoice': case 'voices': case 'ttsServer': return null;
      default: return null; } });
  await p.addInitScript(() => { window.MK_VOICE_PROC = true; window.webkit = { messageHandlers: { multik: { postMessage: m => window.__native(m) } } }; });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => { console.log('  окно:', d.message().slice(0, 160).replace(/\n/g, ' | ')); d.accept(); });
  if (args.includes('--log')) p.on('console', m => console.log('  [стр] ' + m.text().slice(0, 200)));
  p.on('load', () => { st.loads++; });
  let peak = 0; const poll = setInterval(() => { const m = Math.max(0, ...procs().map(x => x.mb)); if (m > peak) peak = m; }, 500);
  await p.goto(`http://localhost:${port}/multik.html`); await p.waitForFunction(() => window.MK3D && MK3D.ready && typeof Lib !== 'undefined' && Lib.data, null, { timeout: 120000 });
  const t0 = Date.now();
  const r0 = await p.evaluate(async ({ txt, hq, fps }) => { MK3D.setQuality(hq ? 'hq' : 'std');
    const r = MKScript.parse(txt, Lib.data); const ep = r.episodes[0]; const v = await Lib.importText(JSON.stringify(ep)); if (v.errors && v.errors.length) return { err: v.errors.join('; ') };
    Lib.data.settings = Object.assign(Lib.data.settings || {}, { narrator: { voice: 'albina', speaker: 'ru_albina', soft: true, rate: 1, pitch: 1 }, fps, res: 720, quality: hq ? 'hq' : 'std' }); await Lib.save();
    const P = Lib.data.projects[Lib.data.projects.length - 1], E = P.episodes[P.episodes.length - 1]; Build.run(P, E); return { ep: E.episode }; }, { txt: fs.readFileSync(scn, 'utf8'), hq: HQ, fps: FPS });
  if (r0.err) { console.log('✘', r0.err); process.exit(1); }
  for (let k = 0; k < 2400 && !st.ended; k++) { await new Promise(r => setTimeout(r, 500)); if (k % 20 === 0) { const bs = await p.evaluate(() => ({ busy: Build.busy, txt: Build.txt || (document.getElementById('bbar') || {}).innerText, q: (Lib.data.settings.buildQueue || []).length, job: !!Lib.data.settings.buildJob, ar: !!Lib.data.settings.autoResume })).catch(e => ({ e: String(e).slice(0, 80) })); console.log('  стр:', JSON.stringify(bs).slice(0, 200)); } if (k % 20 === 0) console.log(`  ${(k / 2) | 0} с: загрузок ${st.loads}, озвучено ${st.voice}, звук ${(st.audioBytes / 1048576).toFixed(1)} МБ, кадров ${st.frames}, этап: ${(st.stages[st.stages.length - 1] || '').slice(0, 60)}`); if (errs.length && k % 20 === 0) console.log('  ошибки:', errs.slice(-2).join(' | ').slice(0, 300)); }
  clearInterval(poll); const dt = (Date.now() - t0) / 1000;
  const lib = st.lib ? JSON.parse(st.lib) : {}; const job = (lib.settings || {}).buildJob;
  await b.close(); srv.close();
  console.log(`Сценарий: ${path.basename(scn)} · ${HQ ? 'как в кино' : 'обычное'} · ${FPS} кадр/с · за ${dt.toFixed(0)} с · пик памяти процесса ${peak} МБ`);
  console.log('этапы:', st.stages.slice(0, 12).join(' → ').slice(0, 600));
  const ok = []; const chk = (c, t) => { ok.push(c); console.log((c ? '✔ ' : '✘ ') + t); };
  chk(!errs.length, 'без ошибок' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
  chk(st.audioBytes > 100000, `звук ушёл в телефон: ${(st.audioBytes / 1048576).toFixed(1)} МБ, ${st.audioChunks} кусков`);
  chk(st.voice > 0 && st.unload > 0, `озвучка: ${st.voice} реплик нейроголосом, голос выгружен`);
  chk(st.loads >= 2, `после звука страница перезапустилась (загрузок: ${st.loads})`);
  chk(st.voiceAfterReload === 0, `после перезапуска серия заново НЕ озвучивалась (реплик: ${st.voiceAfterReload})`);
  chk(!!st.ended && st.ended.frames > 0, `видео дописано: ${st.ended ? st.ended.frames : 0} кадров`);
  chk(!job, 'задание сборки закрыто');
  console.log(ok.every(Boolean) ? 'ИТОГ: сборка проходит' : 'ИТОГ: сборка НЕ проходит'); process.exit(ok.every(Boolean) ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
