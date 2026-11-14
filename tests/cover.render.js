// Обложки: скопировать art/cover.html, core.js и game.js из dist/flagball в COVR_DIR (по умолчанию /tmp/covr),
// затем: node tests/cover.render.js <папка-вывода> [lz] (lz — показать зону ярлыка CrazyGames)
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs');
const OUT = process.argv[2] || '/tmp/covr/out/';
const LZ = process.argv[3] === 'lz';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  for (const [w, h, name] of [[1920, 1080, 'cover_1920x1080.png'], [800, 1200, 'cover_800x1200.png'], [800, 800, 'cover_800x800.png'], [1080, 1620, 'cover_v_1080x1620.png']]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(`file://${process.env.COVR_DIR || '/tmp/covr'}/cover.html?w=${w}&h=${h}${LZ ? '&lz=1' : ''}`);
    await p.waitForFunction(() => window.__done, null, { timeout: 15000 });
    await p.waitForTimeout(300);
    const data = await p.evaluate(() => document.getElementById('out').toDataURL('image/png'));
    fs.writeFileSync(OUT + name, Buffer.from(data.split(',')[1], 'base64'));
    console.log(name, errs.join(';') || 'ok');
    await p.close();
  }
  await b.close();
})();
