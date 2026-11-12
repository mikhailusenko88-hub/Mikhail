// Картинки кнопки «Подписаться» и лапки для Shorts (сервер нарезки накладывает их на ролик): node subpng.js папка
// Рисует тем же кодом, что и в мультике (MK._sub из multik-engine.js). Печатает, куда жмёт лапка в картинке лапки.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
const out = path.resolve(process.argv[2] || '.'); fs.mkdirSync(out, { recursive: true });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.setContent('<html><body></body></html>');
  await p.addScriptTag({ path: path.resolve(__dirname, '../../../Resources/Mebel/multik-engine.js') });
  const r = await p.evaluate(() => { const S = 1, png = (w, h, f) => { const c = document.createElement('canvas'); c.width = w; c.height = h; f(c.getContext('2d')); return c.toDataURL('image/png'); };
    return { red: png(600, 190, g => MK._sub.button(g, 300, 88, S, 0, 9)), done: png(600, 190, g => MK._sub.button(g, 300, 88, S, 20, 9)), paw: png(560, 330, g => MK._sub.paw(g, 70, 120, .95, -1.4, 600)), pawTap: [70, 120] };   /* лапка из-за правого края, длинная лапа */ });
  for (const k of ['red', 'done', 'paw']) fs.writeFileSync(path.join(out, 'sub1_' + k + '.png'), Buffer.from(r[k].split(',')[1], 'base64'));
  console.log('готово:', out, 'лапка жмёт в точке', r.pawTap); await b.close();
})();
