// Студия «Кот Барсик»: сборка серии без телефона. Открывает настоящую страницу приложения (multik.html из ветки mebel-3d)
// в Chrome и подменяет телефон: голос Apple (Пик, Рон и другие) — программой tts, нейроголос — страницей voice.html,
// кадры и звук — в ffmpeg. Картинка и звук получаются тем же кодом, что в приложении.
//   ENG=<клон mebel-3d> VOICE=<клон multik-voice> node studio.js сценарий.txt папка [--std] [--soft] [--res=720] [--fps=25] [--cover]
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path'); const http = require('http');
const { spawn, spawnSync } = require('child_process');
const args = process.argv.slice(2), flag = k => args.includes('--' + k), opt = (k, d) => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : d; };
const pos = args.filter(a => !a.startsWith('--')), SCN = pos[0], OUT = path.resolve(pos[1] || 'out');
const ENG = process.env.ENG, ROOT = path.join(ENG, 'Resources/Mebel'), VDIR = process.env.VOICE || '';
const FFMPEG = process.env.FFMPEG || (() => { try { return require('ffmpeg-static'); } catch (e) { return 'ffmpeg'; } })();
const TTS = path.resolve(process.env.TTS || './tts');
const STD = flag('std'), SOFT = flag('soft'), RES = +opt('res', 1080), FPS = +opt('fps', 25);
fs.mkdirSync(path.join(OUT, 'tts'), { recursive: true });
const T0 = Date.now(), el = () => Math.round((Date.now() - T0) / 1000);
const LOG = path.join(OUT, 'log.txt'); fs.writeFileSync(LOG, '');
const log = (...a) => { const s = `[${String(Math.floor(el() / 60)).padStart(2, '0')}:${String(el() % 60).padStart(2, '0')}] ` + a.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' '); console.log(s); fs.appendFileSync(LOG, s + '\n'); };
const stat = { tts: 0, ttsFail: 0, voice: 0, voiceFail: 0, voiceSec: 0, ttsSec: 0, frames: 0, dialogs: [], errors: [], stages: [] };

// ---- страница приложения и файлы голоса — по http (как в приложении: всё из одной папки) ----
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.wasm': 'application/wasm', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.png': 'image/png', '.jpg': 'image/jpeg' };
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]); const f = /^\/(voice|ort)\//.test(u) && VDIR ? path.join(VDIR, u) : path.join(ROOT, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });

// ---- «телефон»: голос Apple ----
function appleTTS(m) { const t = Date.now(), key = String(m.key || 'k').replace(/[\/\\:]/g, '_'), dir = path.join(OUT, 'tts'), wav = path.join(dir, key + '.wav');
  if (!fs.existsSync(wav)) { const v = m.voice || {};
    if (!fs.existsSync(TTS)) { stat.ttsFail++; return null; }
    const jf = path.join(dir, key + '.json'); fs.writeFileSync(jf, JSON.stringify([{ name: key, text: String(m.text || ''), ipa: v.ipa || [], base: v.base || 'female', pitch: v.pitch, rate: v.rate }]));
    let ok = false; for (let k = 0; k < 2 && !ok; k++) { const r = spawnSync(TTS, [jf, dir, '0'], { timeout: 60000, encoding: 'utf8' }); const caf = path.join(dir, key + '.caf');
      ok = fs.existsSync(caf) && fs.statSync(caf).size > 1000; if (!ok) log('голос Apple: сбой', key, String(m.text).slice(0, 40), (r.stdout || '').slice(-160), (r.stderr || '').slice(-160));
      else spawnSync('afconvert', ['-f', 'WAVE', '-d', 'LEI16', '-c', '1', caf, wav]); }
    if (!ok || !fs.existsSync(wav)) { stat.ttsFail++; return null; } }
  stat.tts++; stat.ttsSec += (Date.now() - t) / 1000; return { wav: fs.readFileSync(wav).toString('base64') }; }

// ---- «телефон»: нейроголос в отдельной странице (как MultikVoiceHost) ----
let browser = null, port = 0, vctx = null, vp = null;
const ENC = `const y=await MKVoice.speak(a.text,a.opts);const n=y.length,b=new Uint8Array(n*2);for(let i=0;i<n;i++){let v=Math.max(-1,Math.min(1,y[i]));v=Math.round(v<0?v*32768:v*32767);b[2*i]=v&255;b[2*i+1]=(v>>8)&255;}let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return{pcm:btoa(s),n:n,last:MKVoice.lastText||''};`;
async function voiceSpeak(m) { const t = Date.now();
  try { if (!vp) { vctx = await browser.newContext(); vp = await vctx.newPage(); vp.on('pageerror', e => log('страница голоса: ошибка', String(e.message).slice(0, 200))); await vp.goto(`http://localhost:${port}/voice.html`); await vp.waitForFunction(() => window.MKVoice, null, { timeout: 120000 }); }
    const r = await vp.evaluate(new Function('a', 'return (async()=>{' + ENC + '})()'), { text: m.text, opts: m.opts }); stat.voice++; stat.voiceSec += (Date.now() - t) / 1000; return r; }
  catch (e) { stat.voiceFail++; log('нейроголос: сбой', String(e && e.message || e).slice(0, 200)); return { error: String(e && e.message || e) }; } }
async function voiceUnload() { if (vctx) { const c = vctx; vctx = null; vp = null; try { await c.close(); } catch (e) {} } return true; }

// ---- «телефон»: запись видео ----
let ff = null, ffName = '', ffErr = '', ffFrames = 0, ffT0 = 0, waiters = [], videos = [];
function videoBegin(m) { const name = String(m.name || 'Серия'), dir = path.join(OUT, 'video'); fs.mkdirSync(dir, { recursive: true }); const out = path.join(dir, name + '.mp4'), fps = String(m.fps || 25);
  const a = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', fps, '-c:v', 'mjpeg', '-i', '-'];
  if (m.audioSrc) a.push('-ss', String(m.audioFrom || 0), '-i', path.join(OUT, m.audioSrc)); else a.push('-i', path.join(OUT, 'audio.wav'));
  a.push('-map', '0:v', '-map', '1:a', '-vf', 'scale=in_color_matrix=bt601:in_range=full:out_color_matrix=bt709:out_range=tv,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-g', String(2 * +fps), '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart'); if (m.audioSrc) a.push('-shortest'); a.push(out);
  if (ff) { try { ff.kill('SIGKILL'); } catch (e) {} }
  ff = spawn(FFMPEG, a, { stdio: ['pipe', 'ignore', 'pipe'] }); ffErr = ''; ff.stderr.on('data', d => { ffErr += d; }); ff.stdin.on('error', e => { ffErr += 'stdin: ' + e.message; });
  ffName = name; ffFrames = 0; ffT0 = Date.now(); log('видео: начало', name, m.w + '×' + m.h, fps + ' к/с'); return { ok: true, frames: 0 }; }
async function videoFrame(m) { if (!ff) return 0; if (m.i !== ffFrames) return -ffFrames - 1;
  const buf = Buffer.from(m.d, 'base64'); ffFrames++; stat.frames++;
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  if (ffFrames % 500 === 0) log('кадр', ffFrames, `${((Date.now() - ffT0) / ffFrames).toFixed(0)} мс/кадр`);
  return 1; }
async function videoEnd(m) { if (!ff) return { error: 'нет записи' }; const f = ff, name = ffName; ff = null;
  const code = await new Promise(r => { f.on('close', r); f.stdin.end(); }); const p = path.join(OUT, 'video', name + '.mp4');
  if (m && m.comment) fs.writeFileSync(path.join(OUT, 'video', name + '.txt'), String(m.comment));
  const ok = code === 0 && fs.existsSync(p) && fs.statSync(p).size > 10000; const v = { name, path: 'video/' + name + '.mp4', frames: ffFrames, sec: Math.round((Date.now() - ffT0) / 1000), ok, err: ffErr.slice(-400) };
  videos.push(v); log('видео: конец', v); waiters.splice(0).forEach(w => w(v)); return ok ? { path: v.path } : { error: 'ffmpeg: ' + ffErr.slice(-200) }; }
const nextVideo = (ms) => new Promise((res, rej) => { waiters.push(res); setTimeout(() => rej(new Error('время вышло: видео не закончено')), ms); });

// ---- мост приложения ----
let libJson = null, audioFile = path.join(OUT, 'audio.wav');
async function native(m) { const c = m && m.cmd;
  switch (c) {
    case 'load': return libJson;
    case 'save': libJson = m.json; return true;
    case 'stage': if (m.text && stat.stages[stat.stages.length - 1] !== m.text) { stat.stages.push(m.text); } return true;
    case 'resolveVoice': return { id: '', name: 'Milena (студия)' };
    case 'voices': return [{ name: 'Milena', id: '', quality: 'обычный' }];
    case 'tts': return appleTTS(m);
    case 'voiceSpeak': return voiceSpeak(m);
    case 'voiceUnload': return voiceUnload();
    case 'audioChunk': { const d = Buffer.from(m.d || '', 'base64'); if (m.first) fs.writeFileSync(audioFile, d); else fs.appendFileSync(audioFile, d); return true; }
    case 'videoBegin': return videoBegin(m);
    case 'videoFrame': return videoFrame(m);
    case 'videoEnd': return videoEnd(m);
    case 'videoCancel': if (ff && !(m && m.keep)) { try { ff.kill('SIGKILL'); } catch (e) {} ff = null; } log('видео: отмена', m || {}); return true;
    case 'writeFile': { const p = path.join(OUT, 'files', String(m.path || 'file').replace(/\.\./g, '_')); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.from(m.d || '', 'base64')); if (m.note) fs.writeFileSync(p + '.txt', String(m.note)); return { path: 'files/' + m.path }; }
    case 'fetch': try { const r = await fetch(m.url); return r.ok ? await r.text() : null; } catch (e) { return null; }
    case 'thermal': return 0;
    case 'parked': return false;
    case 'crashInfo': return null;
    case 'appInfo': return { build: 'студия', version: process.env.ENGINE || '' };
    case 'keepAwake': case 'buildDone': case 'share': case 'copy': case 'removeFile': case 'speak': return true;
    default: return null; } }

(async () => {
  await new Promise(r => srv.listen(0, r)); port = srv.address().port;
  const gpu = SOFT ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'];
  browser = await chromium.launch(Object.assign({ headless: true, timeout: 180000, args: gpu.concat(['--autoplay-policy=no-user-gesture-required']) }, SOFT ? {} : { channel: 'chromium' }));
  const ctx = await browser.newContext({ viewport: { width: 430, height: 900 } });
  await ctx.addInitScript(() => { window.webkit = { messageHandlers: { multik: { postMessage: m => window.__native(m) } } }; });
  const page = await ctx.newPage(); await page.exposeFunction('__native', native);
  page.on('pageerror', e => { const s = String(e.message).slice(0, 300); if (stat.errors.length < 30) stat.errors.push(s); log('ошибка страницы:', s); });
  page.on('console', m => { const t = m.text(); if (m.type() === 'error' || /^(vocal|decode|нейроголос|омографы|БАРС|3D не|студия)/.test(t)) log('страница:', t.slice(0, 300)); });
  page.on('dialog', d => { const s = d.type() + ': ' + d.message().slice(0, 300).replace(/\n/g, ' | '); stat.dialogs.push(s); log('окно:', s); d.accept().catch(() => {}); });
  await page.goto(`http://localhost:${port}/multik.html`);
  await page.waitForFunction(() => typeof Lib !== 'undefined' && Lib.data && window.MK3D && MK3D.ready, null, { timeout: 180000 });
  const gl = await page.evaluate(() => { const c = document.createElement('canvas'), g = c.getContext('webgl2') || c.getContext('webgl'); if (!g) return 'нет WebGL'; const e = g.getExtension('WEBGL_debug_renderer_info'); return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : '?'; });
  log('страница готова; видеокарта:', gl);
  const start = await page.evaluate(async ([txt, q, res, fps]) => {
    const R = MKScript.parse(txt, Lib.data); if (!R.episodes || !R.episodes.length) return { err: 'в сценарии нет серий', errors: R.errors };
    const ep = R.episodes[0], v = await Lib.importText(JSON.stringify(ep), true); if (v && v.errors && v.errors.length) return { err: v.errors };
    Lib.data.settings = Object.assign(Lib.data.settings || {}, { res, fps, quality: q }); try { MK3D.setQuality(q); } catch (e) {} await Lib.save();
    const P = Lib.data.projects.find(p => p.series === ep.series), E = P.episodes.find(e => e.episode === ep.episode);
    // для приёмки: чистые голоса героев (до музыки) и расписание реплик — в момент сведения звука
    const mix0 = MK.mixAudio; MK.mixAudio = async function (tl, bufs) { try {
      const names = {}; for (const id in Lib.data.characters) names[id] = (Lib.data.characters[id].spec || {}).name || id; names['Р'] = 'Рассказчик';
      const by = {}; for (const s of tl.speech) { const b = bufs && bufs[s.key]; if (!b || s.vocal) continue; (by[s.who] = by[s.who] || []).push({ s, b }); }
      for (const who in by) { const top = by[who].filter(x => x.b.duration > 1.2).sort((a, b) => b.b.duration - a.b.duration).slice(0, 5); let k = 0;
        for (const { s, b } of top) await Native.call('writeFile', { path: `voices/${names[who] || who}_${k++}.wav`, d: b64(MK.wav(b)), note: s.text }); }
      const J = { dur: tl.dur, names, speech: tl.speech.map(s => ({ t: +s.t.toFixed(3), dur: +s.dur.toFixed(3), who: s.who, name: names[s.who] || s.who, text: s.text, vocal: !!s.vocal })), segs: tl.segs.map(g => ({ t0: +g.t0.toFixed(3), kind: g.kind, loc: g.lkey || '' })) };
      await Native.call('writeFile', { path: 'speech.json', d: btoa(unescape(encodeURIComponent(JSON.stringify(J)))) });
    } catch (e) { console.log('студия: голоса не сохранены', e && e.message); } return mix0.call(this, tl, bufs); };
    Build.run(P, E);
    return { ok: true, series: ep.series, episode: ep.episode, title: ep.title, scenes: ep.scenes.length, errors: R.errors, unknownWords: R.unknownWords, unknownObjects: R.unknownObjects, unknownNames: R.unknownNames };
  }, [fs.readFileSync(SCN, 'utf8'), STD ? 'std' : 'hq', RES, FPS]);
  log('серия принята:', start); if (!start.ok) { fs.writeFileSync(path.join(OUT, 'result.json'), JSON.stringify({ ok: false, start, stat }, null, 1)); await browser.close(); process.exit(3); }
  let last = ''; const tick = setInterval(async () => { try { const t = await page.evaluate(() => Build.txt + ' · ' + document.getElementById('bbS').textContent); if (t !== last) { last = t; log(t.slice(0, 160)); } } catch (e) {} }, 30000);
  let video = null, err = null; try { video = await nextVideo(+opt('limit', 100) * 60000); } catch (e) { err = String(e.message || e); log('СБОЙ:', err); }
  clearInterval(tick); await new Promise(r => setTimeout(r, 1500));
  let card = null; try { card = await page.evaluate(([se, n]) => { const P = Lib.data.projects.find(p => p.series === se), E = P && P.episodes.find(e => e.episode === n); return E ? { status: E.status, dur: E.dur, video: E.video, voiceFb: E.voiceFb, made: E.made, perf: Lib.data.settings.buildPerf } : null; }, [start.series, start.episode]); } catch (e) {}
  // обложка — кнопкой приложения (постер), если просили
  if (video && video.ok && flag('cover')) { try { await page.evaluate(async ([se, n]) => { const P = Lib.data.projects.find(p => p.series === se), E = P.episodes.find(e => e.episode === n); await Cover.make(P, E, null); }, [start.series, start.episode]); log('обложка приложения готова'); } catch (e) { log('обложка приложения: сбой', String(e.message).slice(0, 200)); } }
  if (libJson) fs.writeFileSync(path.join(OUT, 'lib.json'), libJson);
  const res = { ok: !!(video && video.ok), err, start, video, card, stat: Object.assign({}, stat, { ttsSec: Math.round(stat.ttsSec), voiceSec: Math.round(stat.voiceSec) }), gl, total_sec: el(), mode: STD ? 'обычное' : 'как в кино', res: RES, fps: FPS };
  fs.writeFileSync(path.join(OUT, 'result.json'), JSON.stringify(res, null, 1)); log('ИТОГ', res.ok ? 'готово' : 'не готово', `за ${Math.floor(el() / 60)} мин ${el() % 60} с`);
  await browser.close(); srv.close(); process.exit(res.ok ? 0 : 1);
})().catch(e => { log('СБОЙ студии:', String(e && e.stack || e).slice(0, 600)); process.exit(2); });
