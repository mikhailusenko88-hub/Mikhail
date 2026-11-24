// Гараж: кадры и проверка покупок в настоящем Chrome (объёмный вид программно)
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const DIR = path.resolve(__dirname, '../../' + (process.env.HOOK_DIR || 'g8-hook3d')), OUT = process.argv[2] || '/tmp/gar';
require('fs').mkdirSync(OUT, { recursive: true });
const SIZES = { phone: [390, 844], desk: [1280, 720], land: [844, 390], small: [320, 568] };
(async () => {
  const only = process.argv.slice(3).length ? process.argv.slice(3) : Object.keys(SIZES);
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of only) {
    const [w, h] = SIZES[name], touch = w < 900;
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => (m.type() === 'error' || m.type() === 'warning') && errs.push(m.type() + ': ' + m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1200);
    const shot = async (n) => { await p.waitForTimeout(1500); await p.screenshot({ path: path.join(OUT, name + '-' + n + '.png') }); };
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__hook.btns.find((q) => q.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { errs.push('нет кнопки ' + id); return; } await p.mouse.click(q[0], q[1]); await p.waitForTimeout(250); };
    const st = () => p.evaluate(() => JSON.stringify(window.__hook.save()));
    await shot('0menu');
    await tap('garage'); await shot('1truck');
    const log = [];
    await tap('g:act'); log.push('купить без монет: ' + await st());            // не должно купиться
    await tap('g:item:2'); await shot('2rig-try');
    await tap('g:act'); log.push('тягач без монет: ' + await st());
    await p.evaluate(() => window.__hook.coins(3000));
    await tap('g:act'); log.push('тягач за 900: ' + await st()); await shot('3rig');
    await tap('g:item:1'); await tap('g:act'); log.push('джип без звёзд: ' + await st()); await shot('4jeep-try');
    await tap('g:tab:1'); await tap('g:item:1'); await shot('5monster-try'); await tap('g:act');
    await tap('g:item:2'); await tap('g:act'); await shot('6gold');
    await tap('g:item:3'); await tap('g:act'); await shot('7spikes');
    await tap('g:tab:2'); await shot('8colors'); await tap('g:item:1'); await tap('g:act'); await shot('9blue');
    await tap('g:item:5'); await shot('10black-try');
    await tap('g:tab:3'); await tap('g:up:eng'); await tap('g:up:eng'); await tap('g:up:winch'); await shot('11ups');
    log.push('после покупок: ' + await st());
    await tap('g:back'); await shot('12menu');
    await p.evaluate(() => window.__hook.start(false, 0)); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(1500); await p.evaluate(() => { window.__hook.dbg.freeze = true; }); await p.keyboard.up('ArrowRight'); await shot('13play');
    const cfg = await p.evaluate(() => JSON.stringify(window.__hook.S.cfg));
    console.log(name, errs.length ? errs.slice(0, 5) : 'без ошибок', '\n ' + log.join('\n ') + '\n cfg ' + cfg);
    await ctx.close();
  }
  await b.close();
})();
