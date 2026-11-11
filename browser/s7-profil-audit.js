// Аудит профиля компании на Авито: что заполнено, чего нет. Ничего не меняет.
// Страницы кабинета открываются по очереди в скрытом фрейме (SPA), текст — в sessionStorage.nd_prof.
// Запуск + чтение журнала = 2 подтверждения.
sessionStorage.setItem('nd_prof', '');
const L = s => sessionStorage.setItem('nd_prof', (sessionStorage.getItem('nd_prof') || '') + s + '\n');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const norm = s => (s || '').replace(/ /g, ' ').replace(/[ \t]+/g, ' ').trim();
const SKIP = /^(Мои объявления|Избранное|Сообщения|Уведомления|Кошел|Платные услуги|Бухгалтерия|Заказы|Мои отзывы|Бонусы|Портал призов|Приглашайте|Мои резюме|Подработка|Портфолио|Авито Аукцион|Гараж|Сравнение цен|Спецпредложения|Рассылки|#яПомогаю|Добрые подписки|Защита профиля)/;
async function load(url) {
  const fr = document.createElement('iframe');
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin');
  fr.style.cssText = 'position:fixed;left:-3000px;top:0;width:1280px;height:1800px';
  fr.src = url; document.body.appendChild(fr);
  let d = null;
  for (let i = 0; i < 30; i++) { await sleep(500); try { d = fr.contentDocument; if (d && d.body && d.body.innerText.length > 800) break; } catch (e) {} }
  await sleep(3500);
  let txt = '', links = [], path = '?';
  try {
    d = fr.contentDocument; path = fr.contentWindow.location.pathname + fr.contentWindow.location.search;
    const drop = ['header', 'footer', '[data-marker="profile-sidebar"]', '[data-marker^="header"]', '[data-marker^="footer"]', '[data-marker="mini-messenger"]', '[data-marker^="navigation"]'];
    const clone = d.body.cloneNode(true);
    drop.forEach(s => clone.querySelectorAll(s).forEach(e => e.remove()));
    d.body.appendChild(clone); clone.style.cssText = 'position:absolute;left:-9999px;width:1200px';
    txt = norm(clone.innerText).replace(/\n\s*\n+/g, '\n').replace(/\n/g, ' | ');
    clone.remove();
    txt = txt.replace(/Помощь \| Безопасность \| Реклама на сайте.*$/, '');
    links = [...d.querySelectorAll('a[href]')].filter(a => !a.closest('header,footer,[data-marker="profile-sidebar"],[data-marker^="header"],[data-marker^="footer"]')).map(a => [norm(a.innerText).split('\n')[0], a.getAttribute('href')]).filter(x => x[0] && x[0].length < 50 && /^\/(profile|pro|account|brands|business|settings|delivery)/.test(x[1]));
  } catch (e) { txt = 'не читается: ' + e.message; }
  fr.remove();
  return { txt, links, path };
}
(async () => {
  try {
    const side = [...document.querySelectorAll('[data-marker="profile-sidebar"] a[href]')].map(a => [norm(a.innerText).split('\n')[0], a.getAttribute('href')]).filter(x => x[0] && !SKIP.test(x[0]));
    L('МЕНЮ: ' + side.map(x => x[0] + ' → ' + x[1]).join(' ; '));
    const seen = new Set(); const queue = side.map(x => x[1]);
    queue.push('/brands/41c3cda03dbcc4779122153b28a75b36');
    let n = 0;
    while (queue.length && n < 16) {
      const u = queue.shift(); const key = u.split('#')[0];
      if (seen.has(key)) continue; seen.add(key); n++;
      const r = await load(u);
      L('\n=== ' + u + ' (' + r.path + ')\n' + r.txt.slice(0, 1600));
      if (r.links.length) L('ссылки: ' + r.links.slice(0, 25).map(x => x[0] + ' → ' + x[1]).join(' ; '));
      if (/\/profile\/(settings|basic|info|company|edit)/.test(u) || /Управление профилем/.test(side.find(x => x[1] === u)?.[0] || '')) r.links.forEach(x => { if (!seen.has(x[1].split('#')[0]) && !queue.includes(x[1])) queue.push(x[1]); });
    }
    L('\nВСЁ');
  } catch (e) { L('ОШИБКА ' + String(e && e.stack || e).slice(0, 300)); }
})();
'аудит запущен';
