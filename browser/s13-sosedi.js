// Обзор продавцов-соседей на Авито за 2 подтверждения (запуск + чтение). Навык avito-poisk-rost.
// 1) по запросам QS собирает продавцов из первых NTOP карточек: рейтинг и отзывы, места, продвинуто ли, примеры товаров;
//    ONLY — регулярное выражение по заголовку карточки (прямые соседи по материалу), '' — брать всех;
// 2) открывает профили NSELL продавцов с наибольшим числом отзывов (отзывы — замена числу продаж, самих продаж Авито не показывает):
//    подписчики, с какого года, активные и завершённые объявления, первые NITEMS товаров с ценами.
// Журнал — sessionStorage.nd_log13, результат — sessionStorage.nd_sell13. Проверено 13.11.2026 (9 профилей и 4 запроса — 2,5 минуты, без блокировки).
// Товары на страницах профилей не размечены как [data-marker="item"] — берём ссылки вида …_<номер объявления>.
(() => {
const QS = ['панели дюрополимер', 'плинтус напольный под покраску', 'стеновые панели полистирол', 'панели из дюрополимера под покраску'];
const ONLY = /дюрополимер|полистирол|полиуретан/i;
const KNOWN = {   // кого смотреть всегда, даже если не попал в выдачу
  '/brands/9b74c0149fa35c68ab3583d2482cccd3': 'Сергей (панель дюрополимер 3 м)',
  '/brands/544ffd9a46ae4cb7b0de074a6ec6d7e3': 'Елена Цицианова (панели из дюрополимера)',
  '/brands/e6722563236e2eed0c7215d87dd4b379': 'Карен (3D-панели из дюрополимера)',
  '/brands/i189669386': 'Konstantin (плинтус дюрополимер)',
};
const NTOP = 25, NSELL = 9, NITEMS = 24;
const OURS = ['8402676722', '8530976650', '8546190071', '8523521242', '8495178294', '8068817087'];
const SS = sessionStorage; SS.setItem('nd_log13', ''); SS.setItem('nd_sell13', '');
const L = (...a) => { SS.setItem('nd_log13', (SS.getItem('nd_log13') || '') + new Date().toTimeString().slice(0, 8) + ' ' + a.join(' ') + '\n'); };
const S = s => SS.setItem('nd_sell13', (SS.getItem('nd_sell13') || '') + s + '\n');
const mc = new MessageChannel(); let wake = null;
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const until = async (cond, ms, step = 300) => { const t = Date.now() + ms; while (Date.now() < t) { let ok = false; try { ok = cond(); } catch (e) {} if (ok) return true; await sleep(step); } return false; };
function mk(url) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_fr';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:1366px;height:2400px;z-index:2147483647;background:#fff;border:0;opacity:0.02;pointer-events:none';
  fr.src = url; document.body.appendChild(fr); return fr;
}
const blocked = d => { try { const t = (d.title || '') + ' ' + ((d.body && d.body.innerText) || '').slice(0, 300); return /Доступ ограничен|проблема с IP|не робот/i.test(t) ? t.replace(/\s+/g, ' ').slice(0, 120) : ''; } catch (e) { return ''; } };
const itemLinks = d => [...d.querySelectorAll('a[href]')].filter(a => /_\d{9,11}(\?|$)/.test(a.getAttribute('href') || ''));
(async () => {
  try {
    const sellers = {};
    Object.entries(KNOWN).forEach(([h, n]) => { sellers[h] = { name: n, href: h, rt: '', rev: 0, pos: [], ex: [] }; });
    for (const q of QS) {
      const fr = mk('/sankt-peterburg?q=' + encodeURIComponent(q));
      await until(() => { const dd = fr.contentDocument; return dd && (dd.querySelectorAll('[data-marker="item"]').length >= 30 || blocked(dd)); }, 20000);
      await sleep(900);
      const d = fr.contentDocument; if (blocked(d)) { L('БЛОК на поиске', q); break; }
      [...d.querySelectorAll('[data-marker="item"]')].slice(0, NTOP).forEach((c, i) => {
        const id = (c.getAttribute('data-item-id') || c.id || '').replace(/\D/g, ''); if (OURS.includes(id)) return;
        const full = (c.innerText || '').replace(/\s+/g, ' ');
        const t = ((c.querySelector('[itemprop="name"],[data-marker="item-title"]') || {}).innerText || '').trim();
        const a = [...c.querySelectorAll('a[href]')].find(x => /\/(brands|user)\//.test(x.getAttribute('href') || '')); if (!a) return;
        const href = (a.getAttribute('href') || '').split('?')[0];
        if (!sellers[href] && ONLY && !ONLY.test(t)) return;
        const rt = (full.match(/\d,\d · \d+ отзыв\S*/) || full.match(/\d+ завершённ\S+ объявлени\S+/) || [''])[0];
        const s = sellers[href] || (sellers[href] = { name: (a.innerText || '').trim().replace(/\s+/g, ' ').replace(/ \d,\d · .*$/, '').slice(0, 36), href, rt: '', rev: 0, pos: [], ex: [] });
        if (rt) { s.rt = rt; const m = rt.match(/· (\d+) отзыв/); s.rev = m ? +m[1] : 0; }
        const pe = c.querySelector('[itemprop="price"]');
        s.pos.push(q.split(' ').slice(0, 2).join(' ') + ' №' + (i + 1) + (/Продвинуто/.test(full) ? 'П' : ''));
        if (s.ex.length < 3) s.ex.push(t.slice(0, 40) + ' ' + (pe ? pe.getAttribute('content') : ''));
      });
      await sleep(1200 + Math.random() * 800);
    }
    const list = Object.values(sellers).sort((a, b) => b.rev - a.rev);
    S('# Продавцы в первых ' + NTOP + ': ' + list.length + '. П = продвинуто');
    list.forEach(s => S('- ' + s.name + ' | ' + s.rt + ' | ' + s.pos.join(', ') + ' | ' + s.ex.join(' / ') + ' | ' + s.href));
    for (const s of list.slice(0, NSELL)) {
      const fr = mk(s.href);
      await until(() => { const dd = fr.contentDocument; return dd && dd.readyState === 'complete' && (itemLinks(dd).length >= 6 || blocked(dd)); }, 12000);
      await sleep(1200);
      const d = fr.contentDocument; if (blocked(d)) { L('БЛОК на профиле', s.name); break; }
      const body = (d.body.innerText || ''), facts = [];
      [/\d,\d\s*\d+\s+отзыв\S*/, /\d+\s+подписчик\S*/, /На Авито с [а-я]+ \d{4}/, /Отвечает[^\n]{0,36}/, /Надёжный продавец/, /Реквизиты проверены|Документы проверены/].forEach(re => { const m = body.match(re); if (m) facts.push(m[0].replace(/\s+/g, ' ').trim()); });
      const tabs = [...new Set([...d.querySelectorAll('[data-marker*="tab"],[role=tab],a')].map(e => (e.innerText || '').trim().replace(/\s+/g, ' ')).filter(x => /^(Активные|Завершённые|Объявления|Отзывы) \d/.test(x) && x.length < 24))].slice(0, 4);
      const by = {};   // у одного объявления несколько ссылок: фото («Ещё 5 фото») и заголовок — берём самую содержательную
      for (const a of itemLinks(d)) {
        const id = ((a.getAttribute('href') || '').match(/_(\d{9,11})(\?|$)/) || [])[1]; if (!id) continue;
        let t = (a.getAttribute('title') || a.innerText || '').trim().replace(/\s+/g, ' ').replace(/^Объявление «|»( \d+ фотографи\S+)?$/g, '');
        if (/^Ещё \d+ фото/.test(t)) t = '';
        let e = a, txt = '';
        for (let i = 0; i < 7 && e.parentElement; i++) { e = e.parentElement; txt = (e.innerText || '').replace(/\s+/g, ' ').trim(); if (/₽/.test(txt) && txt.length > 12) break; }
        const pr = (txt.match(/(\d[\d\s]*)\s*₽/) || [])[1];
        const o = by[id] || (by[id] = { t: '', pr: '' });
        if (t.length > o.t.length) o.t = t;
        if (pr && !o.pr) o.pr = pr.replace(/\s/g, '');
      }
      const items = Object.values(by).filter(o => o.t).slice(0, NITEMS).map(o => o.t.slice(0, 44) + ' — ' + (o.pr || '?'));
      S('\n## ' + s.name + ' | ' + s.rt + ' | ' + s.href + '\nфакты: ' + [...new Set(facts)].join(' | ') + ' | ' + tabs.join(' | ') + '\nтовары (' + items.length + ' из ' + Object.keys(by).length + ' на странице): ' + items.join(' ; '));
      L('профиль', s.name, '| объявлений на странице', Object.keys(by).length, '| с заголовком', items.length);
      await sleep(1200 + Math.random() * 800);
    }
    document.getElementById('nd_fr')?.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено';
})();
// Чтение: (sessionStorage.getItem('nd_log13') || '') + '\n=====\n' + (sessionStorage.getItem('nd_sell13') || '')
