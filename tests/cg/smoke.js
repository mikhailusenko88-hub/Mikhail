// Первый заход «как на CrazyGames»: вошедший игрок (рус., Казахстан) и гость (нем., Германия)
const H = require('./harness');
(async () => {
  const b = await H.launch();
  const A = await H.player(b, { user: { username: 'CoolKid99', profilePictureUrl: 'x' }, locale: 'ru-RU', country: 'KZ' });
  const G = await H.player(b, { user: null, locale: 'de-DE', country: 'DE', mobile: true, device: 'mobile' });
  await A.frame.waitForTimeout(3500);
  for (const [n, p] of [['A', A], ['G', G]]) {
    console.log(n, JSON.stringify(await p.st()));
    console.log(n, 'nick/skin', JSON.stringify(await p.ev(() => ({ fb: __dbgOnline().fb, name: window.bridge && window.bridge.player && window.bridge.player.name, auth: window.bridge && window.bridge.player && window.bridge.player.isAuthorized, plang: window.bridge && window.bridge.platform.language, dev: window.bridge && window.bridge.device && window.bridge.device.type }))));
    console.log(n, 'cg', JSON.stringify(await p.cg()));
    console.log(n, 'ext', p.ext.join(' '), 'errs', p.errs.join(' | '));
  }
  await A.shot('smoke_A'); await G.shot('smoke_G');
  // клик мимо игры (по боковой кнопке страницы) — игра не должна замирать
  const m0 = await A.ev(() => Core.realT);
  await A.page.click('#like'); await A.page.waitForTimeout(1500);
  console.log('after blur', JSON.stringify(await A.st()), 'realT moved', (await A.ev(() => Core.realT)) - m0);
  await b.close();
})();
