// Быстрый прогон раундов «как человек» (__chase): когда съедена первая страна, место в конце, победа ли
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  p.on('pageerror', (e) => console.log('PAGEERR', e.message));
  await p.goto('http://localhost:8765/g5-io/index.html'); await p.waitForTimeout(900);
  for (const n of [1, 2, 3, 5, 8]) {
    const res = [];
    for (let k = 0; k < 8; k++) {
      res.push(await p.evaluate((n) => {
        const C = Core; C.save.level = n; C.save.extra.ioEat = n === 1 ? 0 : 1; C.startLevel(); window.__chase = true;
        let first = -1, t = 0; const W = () => __dbg().W;
        while (C.state === 'play' && t < 200) { C.game.update(1 / 60); t += 1 / 60; if (first < 0 && W().balls[0].alive && W().balls.some((o) => o.eatenBy === W().balls[0])) first = Math.round(W().t * 10) / 10; }
        const w = W(), pl = w.balls[0]; const rk = w.balls.filter((o) => o.alive || o.isPlayer).sort((a, c) => c.m - a.m).indexOf(pl) + 1;
        const r = { st: C.state, first, place: rk, m: Math.round(pl.m), end: __dbg().endKind };
        window.__chase = false; C.state = 'home'; return r;
      }, n));
    }
    const wins = res.filter((r) => r.st === 'win').length, eaten = res.filter((r) => r.end === 'eaten').length;
    const firsts = res.map((r) => r.first).filter((x) => x >= 0);
    console.log('уровень', n, '| побед', wins + '/8', '| съели игрока', eaten, '| первая съеденная страна, с:', firsts.join(' '), '| места:', res.map((r) => r.place).join(' '));
  }
  await b.close();
})();
