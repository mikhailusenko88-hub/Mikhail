// Все размеры окна из требований CrazyGames + телефоны вертикально: игра, смерть, магазин.
const H = require('./harness');
const SIZES = [
  ['d907x510', 907, 510], ['d821x462', 821, 462], ['d1216x684', 1216, 684], ['f1920x1080', 1920, 1080],
  ['m800x450', 800, 450, 1], ['t1080x607', 1080, 607, 1], ['p360x640', 360, 640, 1], ['p390x844', 390, 844, 1], ['p412x915', 412, 915, 1], ['tp768x1024', 768, 1024, 1],
  ['app390x844', 390, 844, 1, 'apple_store'], ['app844x390', 844, 390, 1, 'google_play_store'],
];
(async () => {
  const b = await H.launch();
  const room = 'sz' + Date.now() % 100000;
  const hunter = await H.player(b, { user: { username: 'Hunter' }, inviteParams: { room } });
  const only = process.env.ONLY;
  for (const [name, w, h, mob, app] of SIZES) {
    if (only && !name.includes(only)) continue;
    const ru = name.includes('p390') || name.includes('d821') || name.includes('app');
    const p = await H.player(b, { user: { username: ru ? 'Длинноеимя' : 'LongUserName' }, inviteParams: { room }, locale: ru ? 'ru-RU' : 'en-US', country: ru ? 'KZ' : 'US', mobile: !!mob, device: mob ? 'mobile' : 'desktop', app, view: mob ? { width: w, height: h } : { width: Math.max(1366, w + 260), height: Math.max(768, h + 80) }, frame: mob ? null : { w, h }, full: w >= 1280 && !mob, dpr: 1, adsOn: !!process.env.ADS, ads: 'ok' });
    await p.frame.waitForTimeout(2200);
    await p.shot('sz_' + name + '_play');
    await p.ev(() => { Core.save.coins = 380; Core.coinsShown = 380; });
    const k = await H.kill(p, hunter, 90); await p.frame.waitForTimeout(1300);
    await p.shot('sz_' + name + '_death');
    // все кнопки внутри экрана?
    const out = await p.ev(() => Core.UI.rects.filter((r) => !r.block && (r.x < 0 || r.y < 0 || r.x + r.w > Core.W + 0.5 || r.y + r.h > Core.H + 0.5)).map((r) => r.id + '@' + [r.x, r.y, r.w, r.h].map(Math.round).join(',')));
    await p.tap('shopBtn'); await p.frame.waitForTimeout(500); await p.shot('sz_' + name + '_shop');
    const out2 = await p.ev(() => Core.UI.rects.filter((r) => !r.block && (r.x < 0 || r.y < 0 || r.x + r.w > Core.W + 0.5 || r.y + r.h > Core.H + 0.5)).map((r) => r.id + '@' + [r.x, r.y, r.w, r.h].map(Math.round).join(',')));
    console.log(name, 'killed', k, 'W×H', JSON.stringify(await p.ev(() => [Math.round(Core.W), Math.round(Core.H), Core.safe])), 'off-screen death:', out.join(' ') || '-', 'shop:', out2.join(' ') || '-', 'errs', p.errs.join(' | ') || '-');
    await p.close();
  }
  await b.close();
})();
