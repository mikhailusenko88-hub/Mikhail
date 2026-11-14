// Shorts с арены Flagball Arena: камера-зритель заходит на арену, ждёт конца раунда стран,
// снимает последние CLIP секунд и итог «Раунд выиграла …», добавляет свою музыку и звуки.
// Запуск: node shorts/record.js <папка_вывода>
//   GAME_URL — страница игры (по умолчанию http://localhost:8770/index.html)
//   SERVER   — сервер игры (по умолчанию из страницы), ROOM — комната (main), CLIP — секунд до конца раунда (45)
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const PW = process.env.PLAYWRIGHT || '/opt/npm-tools/node_modules/playwright';
const { chromium } = require(PW);

const OUT = path.resolve(process.argv[2] || 'out');
const GAME_URL = process.env.GAME_URL || 'http://localhost:8770/index.html';
const SERVER = process.env.SERVER || '';
const ROOM = process.env.ROOM || 'main';
const CLIP = +process.env.CLIP || 45;
const AFTER = 6.5; // секунд после итога раунда
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
const flagEmoji = (c) => (c && c.length === 2 ? String.fromCodePoint(...[...c.toUpperCase()].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65)) : '');
const NAMES = { RU: 'Russia', KZ: 'Kazakhstan', UZ: 'Uzbekistan', KG: 'Kyrgyzstan', UA: 'Ukraine', BY: 'Belarus', TR: 'Turkey', US: 'USA', GB: 'UK', DE: 'Germany', FR: 'France', IT: 'Italy', ES: 'Spain', PT: 'Portugal', BR: 'Brazil', AR: 'Argentina', MX: 'Mexico', CN: 'China', JP: 'Japan', KR: 'Korea', IN: 'India', ID: 'Indonesia', VN: 'Vietnam', TH: 'Thailand' };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const frames = path.join(OUT, 'frames'); fs.rmSync(frames, { recursive: true, force: true }); fs.mkdirSync(frames);
  const b = await chromium.launch({ executablePath: fs.existsSync(CHROME) ? CHROME : undefined, args: ['--hide-scrollbars', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 2, locale: 'en-US', ignoreHTTPSErrors: true });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => console.log('PAGEERR', e.message));
  const url = GAME_URL + '?spec&room=' + encodeURIComponent(ROOM) + (SERVER ? '&server=' + encodeURIComponent(SERVER) : '');
  await p.goto(url);
  // ждём подключения и нужного момента раунда
  let st = null;
  for (let i = 0; i < 60; i++) { await p.waitForTimeout(500); st = await p.evaluate(() => __dbgOnline().status); if (st === 'ok') break; }
  if (st !== 'ok') { console.log('нет связи с сервером:', st); process.exit(2); }
  console.log('на арене, ждём', CLIP, 'с до конца раунда');
  for (let i = 0; i < 2000; i++) {
    const rt = await p.evaluate(() => __dir().rt);
    if (rt <= CLIP + 0.6 && rt > CLIP - 3) break;
    await p.waitForTimeout(rt > CLIP + 8 ? 3000 : 150);
  }
  // подписи меняет сама страница — точно по кадрам
  await p.evaluate(() => {
    const t0 = performance.now();
    window.__capT = setInterval(() => {
      const t = (performance.now() - t0) / 1000, d = __dir();
      if (d.banner) window.__cap = { top: '', bottom: 'PLAY FREE: FLAGBALL ARENA', bottomA: 1, bottomSize: 44 };
      else window.__cap = t < 2.8 ? { top: 'IS YOUR COUNTRY HERE?', topSize: 54 } : { top: 'WHICH COUNTRY WINS?', topSize: 58 };
    }, 30);
  });
  // запись кадров
  const cdp = await ctx.newCDPSession(p);
  const list = [];
  let n = 0;
  cdp.on('Page.screencastFrame', async (f) => {
    const fn = path.join(frames, 'f' + String(n++).padStart(5, '0') + '.jpg');
    fs.writeFileSync(fn, Buffer.from(f.data, 'base64')); list.push({ fn, t: f.metadata.timestamp });
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) { /* */ }
  });
  const pt0 = await p.evaluate(() => performance.now() / 1000);
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, everyNthFrame: 1, maxWidth: 1080, maxHeight: 1920 });
  // до итога раунда и ещё немного
  let endAt = 0;
  for (let i = 0; i < 1200; i++) {
    await p.waitForTimeout(100);
    const d = await p.evaluate(() => ({ b: !!__dir().banner, t: performance.now() / 1000 }));
    if (d.b && !endAt) endAt = d.t + AFTER;
    if (endAt && d.t >= endAt) break;
    if ((d.t - pt0) > CLIP + 25) break; // раунд не закончился — хватит
  }
  await cdp.send('Page.stopScreencast');
  const info = await p.evaluate(() => __dir());
  await b.close();
  if (list.length < 30) { console.log('мало кадров:', list.length); process.exit(3); }

  // склейка кадров в 30 к/с (каждый момент — последний пришедший кадр)
  const f0 = list[0].t;
  let txt = '';
  for (let i = 0; i < list.length; i++) { const dur = i + 1 < list.length ? list[i + 1].t - list[i].t : 1 / 30; txt += `file '${list[i].fn}'\nduration ${Math.max(0.001, dur).toFixed(4)}\n`; }
  txt += `file '${list[list.length - 1].fn}'\n`;
  fs.writeFileSync(path.join(OUT, 'list.txt'), txt);
  const duration = Math.round((list[list.length - 1].t - f0 + 1 / 30) * 100) / 100;

  // события для звука (время от начала ролика)
  const rel = (t) => Math.round((t - pt0) * 1000) / 1000;
  const round = info.log.filter((e) => e.k === 'round' && e.t >= pt0).pop();
  const roundAt = round ? rel(round.t) : null;
  const ev = {
    duration, seed: Math.floor(Date.now() / 86400000) % 97,
    eats: info.log.filter((e) => e.k === 'eat' && e.t >= pt0).map((e) => ({ t: rel(e.t), m: e.m })),
    beeps: roundAt ? [5, 4, 3, 2, 1].map((k) => [roundAt - k, 0]).filter((x) => x[0] > 0) : [],
    round_at: roundAt,
  };
  fs.writeFileSync(path.join(OUT, 'events.json'), JSON.stringify(ev));
  const wav = path.join(OUT, 'sound.wav');
  execFileSync('python3', [path.join(__dirname, 'mix.py'), path.join(OUT, 'events.json'), wav], { stdio: 'inherit' });

  const top = round ? (round.top || []) : (info.cs || []);
  const win = round ? round.win : (top[0] && top[0][0]);
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
  const mp4 = path.join(OUT, `arena_${stamp}.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(OUT, 'list.txt'), '-i', wav,
    '-vf', 'scale=1080:1920:flags=lanczos,fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
    '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', mp4]);
  // название и описание
  const vs = top.slice(0, 3).map((c) => flagEmoji(c[0]) + ' ' + (NAMES[c[0]] || c[0])).join(' vs ');
  const meta = {
    file: path.basename(mp4), duration, winner: win, top,
    title: (vs ? `Which country wins? ${vs}` : 'Which country wins this round?') + ' #shorts',
    description: [
      win ? `Round won by ${flagEmoji(win)} ${NAMES[win] || win}!` : '',
      'Real online battle from Flagball Arena: every ball is a country. Eat smaller balls, run from bigger ones, win the round for your flag.',
      'Is your country here? Write it in the comments!',
      '#flagball #countryballs #io #shorts',
    ].filter(Boolean).join('\n\n'),
  };
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 2));
  fs.rmSync(frames, { recursive: true, force: true });
  console.log('готово:', mp4, duration + ' с', '| победа:', win, '| поеданий:', ev.eats.length);
})();
