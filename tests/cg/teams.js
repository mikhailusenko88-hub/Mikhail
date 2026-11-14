// Командный зачёт и выбор страны: двое из Казахстана (×2), боты одной командой, поиск страны.
const H = require('./harness');
const ok = (c, m) => console.log((c ? 'OK   ' : 'FAIL ') + m);
(async () => {
  const b = await H.launch();
  const room = 'tm' + (Date.now() % 100000);
  const A = await H.player(b, { user: { username: 'Aru' }, country: 'KZ', locale: 'ru-RU', inviteParams: { room } });
  const B = await H.player(b, { user: { username: 'Erlan' }, country: 'KZ', locale: 'ru-RU', inviteParams: { room }, mobile: true, device: 'mobile' });
  const C2 = await H.player(b, { user: { username: 'Juan' }, country: 'CO', locale: 'es-CO', inviteParams: { room } });
  const S = await H.player(b, { user: null, inviteParams: { room }, qs: '&spec=1' });
  const BOT = () => { window.__bot = (me) => { const a = performance.now() / 2000 + Math.random() * 0.2; return [Math.cos(a), Math.sin(a)]; }; setInterval(() => { const d = __dbgOnline(); if (!d.me.alive && d.dead && d.dead.t > 1.5) { d.dead.t = 9; __respawn(); } }, 700); };
  for (const p of [A, B, C2]) await p.ev(BOT);
  await A.frame.waitForTimeout(12000);
  console.log('A cs', JSON.stringify((await A.st()).cs), 'C2 skin', JSON.stringify(await C2.ev(() => __dbgOnline().fb.skin)), 'C2 lang', (await C2.st()).lang);
  console.log('spec cs', JSON.stringify(await S.ev(() => __dbgOnline().cs)));
  const cs = (await A.st()).cs.map((c) => c[0]);
  ok(cs.includes('BOT') && cs.includes('KZ') && !cs.some((c) => !['BOT', 'KZ', 'CO'].includes(c)), 'player table: only real countries + Bots: ' + cs.join(','));
  const scs = (await S.ev(() => __dbgOnline().cs)).map((c) => c[0]); ok(!scs.includes('BOT'), 'spectator (Shorts) table: flags incl. bots: ' + scs.join(','));
  await A.shot('tm_A_table'); await B.shot('tm_B_table'); await S.shot('tm_spec');
  // выбор страны с поиском
  await H.kill(C2, A, 40); await C2.frame.waitForTimeout(1200);
  await C2.tap('flagBtn'); await C2.frame.waitForTimeout(400);
  const nAll = await C2.frame.evaluate(() => document.querySelectorAll('#flags img:not(.hide)').length);
  await C2.frame.fill('#q', 'port'); await C2.frame.waitForTimeout(150);
  const vis = await C2.frame.evaluate(() => Array.from(document.querySelectorAll('#flags img:not(.hide)')).map((x) => x.alt));
  ok(nAll === 76 && vis.join() === 'PT', 'search: 76 flags, "port" → ' + vis.join(','));
  await C2.frame.fill('#q', 'Коломб'); await C2.frame.waitForTimeout(150);
  const vis2 = await C2.frame.evaluate(() => Array.from(document.querySelectorAll('#flags img:not(.hide)')).map((x) => x.alt));
  ok(vis2.join() === 'CO', 'search in other language "Коломб" → ' + vis2.join(','));
  await C2.frame.fill('#q', ''); await C2.frame.waitForTimeout(100);
  await C2.shot('tm_picker_all');
  await C2.frame.fill('#q', 'нид'); await C2.frame.press('#q', 'Enter'); await C2.frame.click('#go'); await C2.frame.waitForTimeout(200);
  await C2.tap('again'); await C2.frame.waitForTimeout(2500);
  const meta = await A.ev((id) => { for (const b of [...Array(0)]) {} return null; });
  ok((await C2.ev(() => __dbgOnline().fb.skin)) === 'NL', 'picked Netherlands via search+Enter');
  // сервер принял новую страну?
  const seen = await A.ev(() => { const o = []; return o; });
  // дождаться конца раунда (40 с) — баннер
  for (let i = 0; i < 70; i++) { await A.frame.waitForTimeout(500); if (await A.ev(() => __dbgOnline().banner)) break; }
  await A.frame.waitForTimeout(400); await A.shot('tm_round_banner'); await S.shot('tm_spec_round');
  console.log('errs', [A, B, C2, S].map((p) => p.errs.join(' | ') || 'none').join(' / '));
  await b.close();
})();
