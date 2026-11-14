// Сценарии «как на CrazyGames»: смерть, предложения, магазин, подарок, страна/ник, приглашение,
// реклама включена/не заполнилась, звук от CrazyGames, клик мимо игры.
const H = require('./harness');
const ok = (c, m) => console.log((c ? 'OK   ' : 'FAIL ') + m);
(async () => {
  const b = await H.launch();
  // ---------- 1. Пробный запуск: реклама отключена ----------
  const A = await H.player(b, { user: { username: 'CoolKid99' }, locale: 'ru-RU', country: 'KZ' });            // ноутбук 907×510
  const B = await H.player(b, { user: null, locale: 'en-US', country: 'US', mobile: true, device: 'mobile' }); // телефон
  await A.frame.waitForTimeout(2500);
  ok((await A.st()).rew === false, 'A: ads off on CrazyGames basic launch');
  console.log('kill A (0 coins)', await H.kill(A, B, 70)); await A.frame.waitForTimeout(1200);
  let ids = await A.ids(); console.log('A death ids', ids.join(','));
  ok(!ids.includes('revAd') && !ids.includes('dblAd'), 'A: no ad buttons on death screen');
  await A.shot('f1_death_noads_ru');
  // монеты есть — должно быть «вернуться за 150 монет»
  await A.ev(() => { Core.save.coins = 400; Core.coinsShown = 400; });
  await A.tap('again'); await A.frame.waitForTimeout(2500);
  console.log('kill A (400 coins)', await H.kill(A, B, 90)); await A.frame.waitForTimeout(1200);
  ids = await A.ids(); console.log('A death ids', ids.join(','), JSON.stringify((await A.st()).dead));
  ok(ids.includes('revCoin') && !ids.includes('revAd'), 'A: coin revive offered without ads');
  await A.shot('f1_death_coinrevive_ru');
  const c0 = (await A.st()).coins; await A.tap('revCoin'); await A.frame.waitForTimeout(2500);
  const sA = await A.st(); ok(sA.alive && sA.m >= 30 && sA.coins === c0 - 150, 'A: revived for coins, mass ' + sA.m + ', coins ' + c0 + '→' + sA.coins);
  // магазин без рекламы
  console.log('kill A', await H.kill(A, B, 50)); await A.frame.waitForTimeout(1200);
  await A.tap('shopBtn'); await A.frame.waitForTimeout(500);
  ids = await A.ids(); ok(!ids.includes('adCoins'), 'A: shop has no ad-coins button'); await A.shot('f1_shop_ru');
  await A.tap('acc3'); await A.frame.waitForTimeout(300); await A.tap('shopClose'); await A.frame.waitForTimeout(300);
  // подарок (первый — сразу готов)
  const g0 = (await A.st()).coins; await A.tap('giftBtn'); await A.frame.waitForTimeout(800);
  ok((await A.st()).coins > g0, 'A: gift claimed ' + g0 + '→' + (await A.st()).coins);
  await A.shot('f1_after_gift_ru');
  // смена страны и ника (с пробелом — раньше пробел глушился)
  await A.tap('flagBtn'); await A.frame.waitForTimeout(500);
  await A.frame.click('#flags img[alt="RU"]'); await A.frame.fill('#nick', ''); await A.frame.click('#nick'); await A.page.keyboard.type('Cool Kid');
  await A.shot('f1_change_country_ru');
  await A.frame.click('#go'); await A.frame.waitForTimeout(300);
  ok(await A.ev(() => __dbgOnline().fb.nick === 'Cool Kid' && __dbgOnline().fb.skin === 'RU'), 'A: country RU and nick with space saved: ' + JSON.stringify(await A.ev(() => __dbgOnline().fb.nick)));
  // приглашение
  await A.tap('invBtn'); await A.frame.waitForTimeout(600);
  const clip = await A.frame.evaluate(() => navigator.clipboard.readText().catch((e) => 'ERR ' + e.message));
  ok(/crazygames\.com\/game\/flagball-arena\?room=main/.test(clip), 'A: invite link copied: ' + clip);
  await A.shot('f1_invite_ru');
  await A.tap('again'); await A.frame.waitForTimeout(2500);
  ok((await A.st()).alive, 'A: back in game after play again');
  // звук: CrazyGames выключил звук в настройках
  await A.ev(() => window.__cg.mute(true)); await A.frame.waitForTimeout(200);
  ok(await A.ev(() => Core.platformMuted === true), 'A: platform mute respected');
  await A.ev(() => window.__cg.mute(false));
  // клик мимо игры
  const t0 = await A.ev(() => Core.realT); await A.page.click('#other'); await A.page.waitForTimeout(1200);
  ok((await A.ev(() => Core.realT)) - t0 > 0.8 && !(await A.st()).paused, 'A: keeps running after focus moved out of the game');
  console.log('A cg log', JSON.stringify((await A.cg()).map((x) => x[1] + (x[2] ? ':' + JSON.stringify(x[2]) : ''))));
  console.log('A errs', A.errs.join(' | ') || 'none', 'ext', A.ext.join(' ') || 'none');
  await B.shot('f1_B_play_en');
  console.log('B errs', B.errs.join(' | ') || 'none');
  await A.close();

  // ---------- 2. Полный запуск: реклама включена ----------
  const C = await H.player(b, { user: { username: 'AdFan' }, locale: 'en-GB', country: 'GB', adsOn: true, ads: 'ok' });
  await C.frame.waitForTimeout(2500);
  ok((await C.st()).rew === true, 'C: ads on (full launch build)');
  console.log('kill C', await H.kill(C, B, 80)); await C.frame.waitForTimeout(1200);
  ids = await C.ids(); console.log('C death ids', ids.join(','));
  ok(ids.includes('revAd'), 'C: revive-for-ad offered');
  await C.shot('f2_death_revive_ad_en');
  const ra = await C.rect('revAd'), rg = await C.rect('again');
  ok(ra && rg && Math.abs(ra.w - rg.w) < 1 && Math.abs(ra.h - rg.h) < 1, 'C: "Play again" same size as ad button');
  await C.tap('revAd'); await C.frame.waitForTimeout(700);
  ok((await C.st()).adPlaying === true, 'C: game muted while ad plays');
  await C.frame.waitForTimeout(2500);
  const sC = await C.st(); ok(sC.alive && sC.m >= 30 && !sC.adPlaying, 'C: revived after ad, mass ' + sC.m);
  // следующая смерть — x2 за рекламу
  console.log('kill C', await H.kill(C, B, 60)); await C.frame.waitForTimeout(1200);
  ids = await C.ids(); console.log('C death2 ids', ids.join(','), JSON.stringify((await C.st()).dead));
  if (ids.includes('dblAd')) { const k0 = (await C.st()).coins; await C.tap('dblAd'); await C.frame.waitForTimeout(2500); ok((await C.st()).coins > k0, 'C: x2 coins after ad ' + k0 + '→' + (await C.st()).coins); }
  else ok(false, 'C: x2 offer expected');
  // реклама не заполнилась
  await C.ev(() => { window.__cgAdMode = 'unfilled'; });
  await C.tap('shopBtn'); await C.frame.waitForTimeout(400);
  ids = await C.ids(); ok(ids.includes('adCoins'), 'C: shop has ad-coins button');
  const k1 = (await C.st()).coins; await C.tap('adCoins'); await C.frame.waitForTimeout(800);
  ids = await C.ids(); ok(!ids.includes('adCoins') && (await C.st()).coins === k1, 'C: unfilled ad → no reward, ad button hidden');
  await C.shot('f2_shop_after_unfilled_en');
  await C.tap('shopClose'); await C.frame.waitForTimeout(400); await C.shot('f2_death_after_unfilled_en');
  console.log('C cg log', JSON.stringify((await C.cg()).map((x) => x[1] + (x[2] ? ':' + JSON.stringify(x[2]) : ''))));
  console.log('C errs', C.errs.join(' | ') || 'none', 'ext', C.ext.join(' ') || 'none');
  await C.close();

  // ---------- 3. Играть с друзьями: своя комната, приглашение, переход без перезагрузки ----------
  const P1 = await H.player(b, { user: { username: 'PartyLeader' }, instant: true, locale: 'en-US', country: 'FR' });
  await P1.frame.waitForTimeout(2000);
  const room = await P1.ev(() => (window.__cgLog.filter((x) => x[1] === 'updateRoom').pop() || [])[2]);
  console.log('P1 room', JSON.stringify(room));
  ok(room && /^p[a-z0-9]+$/.test(room.roomId) && room.isJoinable, 'P1: instant multiplayer → own private room, joinable');
  const P2 = await H.player(b, { user: { username: 'Friend1' }, inviteParams: { room: room.roomId }, locale: 'ru-RU', country: 'RU', mobile: true, device: 'mobile' });
  await P2.frame.waitForTimeout(2500);
  const hum = (p) => p.ev(() => { let n = 0; for (const x of __dir ? [] : []) n++; return Array.from(document.querySelectorAll('x')).length; });
  const nh = async (p) => p.ev(() => { const d = __dir(); return d.humans; });
  ok((await nh(P1)) === 2 && (await nh(P2)) === 2, 'P1+P2 in the same private room: ' + (await nh(P1)) + '/' + (await nh(P2)));
  await P1.shot('f3_private_room_P1'); await P2.shot('f3_private_room_P2');
  const P3 = await H.player(b, { user: { username: 'LateFriend' }, locale: 'en-US', country: 'BR' });
  await P3.frame.waitForTimeout(2000);
  ok((await nh(P3)) >= 1, 'P3 in main');
  await P3.ev((r) => window.__cg.join({ room: r }), room.roomId); await P3.frame.waitForTimeout(2500);
  ok((await nh(P1)) === 3, 'P3 joined the private room via join listener without reload: ' + (await nh(P1)));
  console.log('P errs', [P1, P2, P3].map((p) => p.errs.join(' | ') || 'none').join(' / '));
  await P1.close(); await P2.close(); await P3.close(); await B.close();
  await b.close();
})();
