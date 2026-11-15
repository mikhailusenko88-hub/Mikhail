// Проверка раскладки на телефоне: газ/тормоз справа, крюк слева (кнопка и вся левая половина)
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  for (const [vw, vh] of [[390, 844], [844, 390]]) {
    const ctx = await b.newContext({ viewport: { width: vw, height: vh }, hasTouch: true, isMobile: true, locale: 'ru-RU' });
    const p = await ctx.newPage(); await p.goto('file://' + path.resolve(__dirname, '../../g7-hook/index.html')); await p.waitForTimeout(400);
    const r = await p.evaluate(() => {
      window.__hook.start(false);
      const c = document.getElementById('c'), B = Object.fromEntries(window.__hook.buttons.map((q) => [q.id, q]));
      const down = (id, x, y) => c.dispatchEvent(new PointerEvent('pointerdown', { pointerId: id, pointerType: 'touch', clientX: x, clientY: y, bubbles: true }));
      const up = (id) => c.dispatchEvent(new PointerEvent('pointerup', { pointerId: id, pointerType: 'touch', bubbles: true }));
      const mid = (q) => [q.x + q.w / 2, q.y + q.h / 2], out = {};
      down(1, ...mid(B.gas)); out.gas = window.__hook.input(); up(1);
      down(2, ...mid(B.brake)); out.brake = window.__hook.input(); up(2);
      down(3, innerWidth * 0.25, innerHeight * 0.4); out.leftHalf = window.__hook.input(); up(3);
      down(4, ...mid(B.gas)); down(5, ...mid(B.hook)); out.gasAndHook = window.__hook.input(); up(4); up(5);
      down(6, innerWidth * 0.75, innerHeight * 0.4); out.rightEmpty = window.__hook.input(); up(6);
      const pos = Object.fromEntries(Object.entries(B).filter(([k]) => ['gas', 'brake', 'hook', 'pull'].includes(k)).map(([k, q]) => [k, q.x + q.w / 2 > innerWidth / 2 ? 'справа' : 'слева']));
      return { pos, out };
    });
    const f = (o) => Object.entries(o).filter(([, v]) => v).map(([k]) => k).join('+') || '—';
    console.log(vw + 'x' + vh, JSON.stringify(r.pos), 'газ:', f(r.out.gas), '| тормоз:', f(r.out.brake), '| левая половина:', f(r.out.leftHalf), '| газ+крюк:', f(r.out.gasAndHook), '| правая пустая:', f(r.out.rightEmpty));
    await p.screenshot({ path: path.join(__dirname, 'shots', 'touch_' + vw + '.png') });
    await ctx.close();
  }
  await b.close();
})();
