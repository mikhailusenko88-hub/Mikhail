// Ежедневный обход Авито за 2 подтверждения (запуск + чтение): кабинет, места по основным запросам,
// широкие запросы «как ищут люди» (по кругу, 8 в день), продавцы-соседи и профили новых соседей. Навык avito-poisk-rost.
// Идёт 3,5–4 минуты; вызов сразу возвращает «запущено». Журнал — sessionStorage.nd_log15, обзор — sessionStorage.nd_day15.
// Первый полный запуск 14.11.2026: 19 запросов и 4 профиля за 2 мин 53 с, без блокировки, 3 подтверждения (открыть вкладку, запуск, чтение).
// 15.11: вторая страница для основных запросов проверена. Браузер оказался разлогинен: /profile во фрейме ушёл на /#login, кабинет не прочитался,
// а места были сняты без входа (со вчерашними, снятыми со входом, напрямую не сравнивать). Теперь скрипт сам пишет «ВХОД: да/нет»,
// просмотры (всего и за сегодня) берёт ещё и со страниц объявлений — они видны без входа, — и не ходит в профили продавцов из других городов.
// Разовые добавки: EXTRA — запросы, которые надо снять как основные (со второй страницей); WIDE_ON / PROF_ON — выключить широкие запросы и профили.
// 15.11, перемер со входом через 15 минут после замера без входа: по редким запросам места те же (±5), а по частым со входом мы видим себя
// намного выше — «плинтус напольный» №2 со входом и №20 без входа, «плинтус дюрополимер» №7 и №16. Поэтому ANON: те же запросы ещё раз во фрейме
// без куки (credentialless) — «как посторонний». Запуском ещё не проверено; если фрейм не читается, скрипт это напишет и пойдёт дальше.
// Страницы своих объявлений со входом открываются в виде для владельца, счётчиков просмотров там нет — pages() зовём, только когда входа нет.
(() => {
const IDS = { '8402676722': '3-7', '8530976650': '3-15', '8546190071': '3-9', '8523521242': 'A910', '8495178294': 'A703', '8068817087': 'старое' };
// основные запросы — каждый день, набор не менять без причины (иначе не с чем сравнивать)
const CORE = ['реечные панели под дерево', 'плинтус напольный под покраску', 'стеновые панели полистирол', 'реечные панели под покраску',
  'декоративные рейки на стену', 'панели дюрополимер', 'стеновые панели', 'плинтус дюрополимер', 'реечные панели', 'реечные панели для стен', 'плинтус напольный'];
// широкие запросы: как это называют люди (Вордстат по СПб из claude/artdec-semantika-nazvaniya.md); три группы по кругу
const WIDE = [
  ['декоративные рейки', 'рейки на стену', 'стеновые панели под дерево', 'панели для стен', 'плинтус напольный белый', 'панели на стену', 'стеновые панели под покраску', 'декоративные рейки мдф'],   // «ламели на стену» убрали 14.11: в выдаче одни жалюзи
  ['рейки для стен', 'стеновые панели для внутренней отделки', 'реечные панели мдф', 'белые реечные панели', '3d панели для стен', 'плинтус под покраску', 'плинтус 80 мм', 'плинтус широкий'],
  ['акустические панели', 'стеновые панели мдф', 'декоративные панели для стен', 'молдинги на стену', 'молдинги для стен', 'потолочный плинтус', 'плинтус с кабель-каналом', 'скрытый плинтус'],
];
const DAY = Math.floor((Date.now() - Date.parse('2026-11-14T00:00:00+03:00')) / 86400000);
const GROUP = ((DAY % 3) + 3) % 3;          // 14.11 — группа 0, 15.11 — группа 1, 16.11 — группа 2, дальше по кругу; можно задать числом
const NPROF = 4;                             // сколько профилей новых соседей открыть за день
const EXTRA = [];                            // разовые запросы «как основные» (со второй страницей), например после смены заголовка
const WIDE_ON = true, PROF_ON = true;        // false — короткий перемер: только кабинет и основные запросы
const ANON = ['плинтус напольный', 'плинтус дюрополимер', 'реечные панели для стен'];   // эти запросы снять ещё и «как посторонний» (фрейм без куки)
const SEEN = ['/brands/i189669386', '/brands/9b74c0149fa35c68ab3583d2482cccd3', '/brands/e6722563236e2eed0c7215d87dd4b379', '/brands/plintusy', '/brands/i35021401',
  '/brands/i303422686', '/brands/544ffd9a46ae4cb7b0de074a6ec6d7e3', '/brands/arhidea', '/brands/90967ed0df52f22382beaf3e0f587006',
  '/brands/i188920544', '/brands/i122608885', '/brands/i72526920', '/brands/akupanel.ru', '/brands/i200336086', '/brands/6fce8c6bbc94076bfb4ce1c8c3d3fd4e',
  '/brands/i223454591', '/brands/i350145740', '/brands/4e13e6a698f4de9a0380a6a3c5aa2ed6', '/brands/i365350883',
  '/brands/22b0cbf19d8679a2fca050974ba7bbe4', '/brands/2dfafb93c25eb5d799945de7a940e663', '/brands/i260900186', '/brands/comiron'];   // профили уже разобраны (13–14.11: MORUS, «Высота», «Обои панели плинтусы», СТРОЙ-МИКС; 15.11: DKSPROFILE, Panelio, «Интересный выбор», COMIRON) — дописывать сюда после каждого дня
const SKIP = /монтаж|установка|поклейка|покраска|ремонт|остеклен|лестниц|жалюзи|забор|фасад|террас|дпк|кирпич|утеплител|сайдинг|мрамор/i;   // услуги и чужие товары в профили не ходим
const CITY = / в (Екатеринбург|Челябинск|Оренбург|Москв|Казан|Новосибирск|Краснодар|Нижнем|Самар|Ростов|Уф[еы]|Перм|Воронеж|Тюмен|Омск|Красноярск)/i;   // продавцы из других городов, купившие показ в СПб
const SS = sessionStorage; SS.setItem('nd_log15', ''); SS.setItem('nd_day15', '');
const L = (...a) => { SS.setItem('nd_log15', (SS.getItem('nd_log15') || '') + new Date().toTimeString().slice(0, 8) + ' ' + a.join(' ') + '\n'); };
const S = s => SS.setItem('nd_day15', (SS.getItem('nd_day15') || '') + s + '\n');
const mc = new MessageChannel(); let wake = null;   // паузы без setTimeout: при скрытой панели таймеры срабатывают раз в минуту
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const until = async (cond, ms, step = 300) => { const t = Date.now() + ms; while (Date.now() < t) { let ok = false; try { ok = cond(); } catch (e) {} if (ok) return true; await sleep(step); } return false; };
const pause = () => sleep(1600 + Math.random() * 1000);
function mk(url, h, anon) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_fr';
  if (anon) { fr.credentialless = true; fr.setAttribute('credentialless', ''); }   // без куки: Авито видит постороннего
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:1366px;height:' + (h || 900) + 'px;z-index:2147483647;background:#fff;border:0;opacity:0.02;pointer-events:none';
  fr.src = url; document.body.appendChild(fr); return fr;
}
const blocked = d => { try { const t = (d.title || '') + ' ' + ((d.body && d.body.innerText) || '').slice(0, 300); return /Доступ ограничен|проблема с IP|не робот/i.test(t) ? t.replace(/\s+/g, ' ').slice(0, 120) : ''; } catch (e) { return ''; } };
const idOf = c => (c.getAttribute('data-item-id') || c.id || '').replace(/\D/g, '');
const itemLinks = d => [...d.querySelectorAll('a[href]')].filter(a => /_\d{9,11}(\?|$)/.test(a.getAttribute('href') || ''));
const sellers = {};
async function pages() {   // просмотры со страниц объявлений: видны и без входа; заодно — что объявление живо и какой у него заголовок
  S('# СТРАНИЦЫ ОБЪЯВЛЕНИЙ (заголовок | просмотры всего | сегодня | дата)');
  for (const id of Object.keys(IDS)) {
    try {
      const r = await fetch('/' + id, { credentials: 'include' }), h = await r.text();
      const d = new DOMParser().parseFromString(h, 'text/html');
      const g = m => ((d.querySelector('[data-marker="' + m + '"]') || {}).textContent || '').replace(/\s+/g, ' ').trim();
      S(IDS[id] + ' | http ' + r.status + ' | ' + (((d.querySelector('h1') || {}).textContent || d.title || '').replace(/\s+/g, ' ').trim().slice(0, 60)) + ' | ' + g('item-view/total-views') + ' | ' + g('item-view/today-views') + ' | ' + g('item-view/item-date') + (/Доступ ограничен|проблема с IP/i.test(h.slice(0, 4000)) ? ' | БЛОК' : ''));
    } catch (e) { S(IDS[id] + ' | ошибка ' + String(e).slice(0, 80)); }
    await sleep(600);
  }
}
async function cabinet() {
  const fr = mk('/profile');
  const ok = await until(() => { const dd = fr.contentDocument; if (!dd) return false; let h = ''; try { h = fr.contentWindow.location.href; } catch (e) {} return /#login/.test(h) || Object.keys(IDS).filter(id => dd.querySelector('a[href*="' + id + '"]')).length >= 4; }, 30000);
  await sleep(2500);
  const d = fr.contentDocument;
  if (blocked(d)) { S('кабинет: блок'); return; }
  let href = ''; try { href = fr.contentWindow.location.href; } catch (e) {}
  if (/#login/.test(href) || /Вход и регистрация/.test(((d.body && d.body.innerText) || '').slice(0, 1500))) {
    L('НЕ ВОШЛИ'); S('# ВХОД: НЕТ — браузер разлогинен (' + href.replace(/^https:\/\/www\.avito\.ru/, '') + '). Контакты, избранное, кошелёк и сроки не видны; места сняты БЕЗ входа — с замерами со входом напрямую не сравнивать. Войти должен Михаил.');
    return false;
  }
  S('# ВХОД: да');
  S('# КАБИНЕТ (загружен: ' + ok + ') | вкладки: ' + [...d.querySelectorAll('[data-marker*="tab"],[role=tab]')].map(e => (e.innerText || '').trim().replace(/\s+/g, ' ')).filter(x => x && x.length < 40).slice(0, 6).join(' · ') + ' | ' + ((((d.body.innerText || '').match(/Кошел[её]к[^₽]{0,60}₽/) || [''])[0].replace(/\s+/g, ' ')) || 'кошелёк не виден'));
  for (const id of Object.keys(IDS)) {
    const a = d.querySelector('a[href*="' + id + '"]');
    if (!a) { S(IDS[id] + ' — в списке нет'); continue; }
    let e = a, txt = '';
    for (let i = 0; i < 10 && e.parentElement; i++) { e = e.parentElement; txt = (e.innerText || '').trim(); if (txt.length > 160) break; }
    S(IDS[id] + ' | ' + txt.replace(/\s+/g, ' ').replace(/−70% на продвижение.*$/, '').slice(0, 260));   // числа: просмотры всего[+из них сегодня] контакты избранное
  }
  return true;
}
async function serpAnon(q) {   // тот же запрос «как посторонний»: насколько наш аккаунт завышает наши места
  if (!('credentialless' in HTMLIFrameElement.prototype)) { S('  · как посторонний: браузер не умеет фрейм без куки'); return false; }
  const fr = mk('/sankt-peterburg?q=' + encodeURIComponent(q), 900, true), t0 = Date.now();
  let dead = false;
  await until(() => { let dd = null; try { dd = fr.contentDocument; } catch (e) { dead = true; return true; } if (!dd) { if (Date.now() - t0 > 7000) { dead = true; return true; } return false; } return dd.querySelectorAll('[data-marker="item"]').length >= 30 || !!blocked(dd); }, 20000);
  await sleep(900);
  let d = null; try { d = fr.contentDocument; } catch (e) {}
  if (dead || !d) { S('  · как посторонний «' + q + '»: фрейм без куки не читается'); return false; }
  if (blocked(d)) { L('БЛОК на поиске без куки', q); S('  · как посторонний «' + q + '»: блок'); return false; }
  const cards = [...d.querySelectorAll('[data-marker="item"]')];
  const ours = cards.map((c, i) => [idOf(c), i + 1]).filter(x => IDS[x[0]]).map(x => IDS[x[0]] + ' №' + x[1]);
  const guest = /Вход и регистрация/.test(((d.body && d.body.innerText) || '').slice(0, 1500));
  S('  · как посторонний' + (guest ? '' : ' (ВХОД ОСТАЛСЯ — не считать)') + ' «' + q + '»: ' + (ours.join(', ') || 'нет на 1-й стр.') + ' | карточек ' + cards.length + ' | продвинуто в десятке: ' + cards.slice(0, 10).filter(c => /Продвинуто/.test(c.innerText || '')).length);
  return true;
}
async function serp(q, wide, p) {
  const fr = mk('/sankt-peterburg?q=' + encodeURIComponent(q) + (p > 1 ? '&p=' + p : ''));
  await until(() => { const dd = fr.contentDocument; return dd && (dd.querySelectorAll('[data-marker="item"]').length >= 30 || blocked(dd)); }, 20000);
  await sleep(900);
  const d = fr.contentDocument;
  if (blocked(d)) { L('БЛОК на поиске', q); S('!! блок на «' + q + '»'); return false; }
  const cards = [...d.querySelectorAll('[data-marker="item"]')];   // все 50 карточек страницы, не блок catalog-serp
  const ours = cards.map((c, i) => [idOf(c), i + 1]).filter(x => IDS[x[0]]).map(x => IDS[x[0]] + ' №' + ((p > 1 ? (p - 1) * 50 : 0) + x[1]));
  if (p > 1) { S('  · стр. ' + p + ': ' + (ours.join(', ') || 'нас нет и в первых ' + p * 50)); return true; }
  const top = cards.slice(0, 15).map(c => {
    const full = (c.innerText || '').replace(/\s+/g, ' ');
    const t = ((c.querySelector('[itemprop="name"],[data-marker="item-title"]') || {}).innerText || '').trim();
    const pe = c.querySelector('[itemprop="price"]'), pr = pe ? (pe.getAttribute('content') || '') : '';
    const promo = /Продвинуто/.test(full);
    const a = [...c.querySelectorAll('a[href]')].find(x => /\/(brands|user)\//.test(x.getAttribute('href') || ''));
    if (a && !IDS[idOf(c)]) {
      const href = (a.getAttribute('href') || '').split('?')[0], rt = (full.match(/\d,\d · \d+ отзыв\S*/) || [''])[0];
      const s = sellers[href] || (sellers[href] = { name: (a.innerText || '').trim().replace(/\s+/g, ' ').replace(/ \d,\d · .*$/, '').slice(0, 32), rt: '', n: 0, promo: 0, qs: new Set(), ex: t.slice(0, 36) + ' ' + pr, full: t });
      s.n++; if (promo) s.promo++; if (rt) s.rt = rt; s.qs.add(q);
    }
    return { t, pr, promo };
  });
  const cnt = ((d.querySelector('[data-marker="page-title/count"]') || {}).innerText || '').trim();
  S((wide ? '## ' : '- ') + q + ' | всего ' + cnt + ' | НАШИ: ' + (ours.join(', ') || 'нет на 1-й стр.') + ' | продвинуто в десятке: ' + top.slice(0, 10).filter(x => x.promo).length +
    (wide ? '\n   ' + top.slice(0, 6).map((x, i) => (i + 1) + ') ' + x.t.slice(0, 44) + ' ' + x.pr + (x.promo ? ' П' : '')).join(' ; ') : ''));
  return ours.length ? true : 'none';
}
async function profile(href, s) {
  const fr = mk(href, 2400);
  await until(() => { const dd = fr.contentDocument; return dd && dd.readyState === 'complete' && (itemLinks(dd).length >= 6 || blocked(dd)); }, 12000);
  await sleep(1200);
  const d = fr.contentDocument; if (blocked(d)) { L('БЛОК на профиле', s.name); return false; }
  const body = (d.body.innerText || ''), facts = [];
  [/\d,\d\s*\d+\s+отзыв\S*/, /\d+\s+подписчик\S*/, /На Авито с [а-я]+ \d{4}/, /Отвечает[^\n]{0,36}/, /Надёжный продавец/].forEach(re => { const m = body.match(re); if (m) facts.push(m[0].replace(/\s+/g, ' ').trim()); });
  const tabs = [...new Set([...d.querySelectorAll('[data-marker*="tab"],[role=tab],a')].map(e => (e.innerText || '').trim().replace(/\s+/g, ' ')).filter(x => /^(Активные|Завершённые|Объявления|Отзывы) \d/.test(x) && x.length < 24))].slice(0, 4);
  const by = {};
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
  const items = Object.values(by).filter(o => o.t).slice(0, 18).map(o => o.t.slice(0, 42) + ' — ' + (o.pr || '?'));
  S('\n### ' + s.name + ' | ' + s.rt + ' | ' + href + '\n' + [...new Set(facts)].join(' | ') + ' | ' + tabs.join(' | ') + '\nтовары: ' + items.join(' ; '));
  return true;
}
(async () => {
  try {
    L('старт, группа широких запросов', GROUP);
    const logged = await cabinet(); await pause();
    if (!logged) await pages();
    S('\n# ОСНОВНЫЕ ЗАПРОСЫ');
    let ok = true;
    for (const q of CORE.concat(EXTRA)) { ok = await serp(q, false); if (!ok) break; await pause(); if (ok === 'none') { ok = await serp(q, false, 2); if (!ok) break; await pause(); } }
    if (ok && logged && ANON.length) {
      S('\n# КАК ПОСТОРОННИЙ (фрейм без куки)');
      for (const q of ANON) { if (!(await serpAnon(q))) break; await pause(); }
    }
    if (ok && WIDE_ON) {
      S('\n# ШИРОКИЕ ЗАПРОСЫ, группа ' + GROUP + ' (П = продвинуто)');
      for (const q of WIDE[GROUP]) { ok = await serp(q, true); if (!ok) break; await pause(); }
    }
    const list = Object.entries(sellers).map(([h, s]) => ({ h, ...s })).sort((a, b) => b.n - a.n);
    S('\n# ПРОДАВЦЫ в первых 15 (мест / продвинуто / запросов), всего ' + list.length);
    list.filter(s => s.n >= 2).slice(0, 24).forEach(s => S('- ' + s.name + ' | ' + s.rt + ' | ' + s.n + ' / ' + s.promo + ' / ' + s.qs.size + ' | ' + s.ex + ' | ' + s.h + (SEEN.includes(s.h) ? '' : ' | НОВЫЙ')));
    if (ok && PROF_ON) {
      const fresh = list.filter(s => !SEEN.includes(s.h) && !SKIP.test(s.full) && !SKIP.test(s.name) && !CITY.test(s.full)).slice(0, NPROF);
      if (fresh.length) S('\n# ПРОФИЛИ НОВЫХ СОСЕДЕЙ');
      for (const s of fresh) { if (!(await profile(s.h, s))) break; await pause(); }
    }
    document.getElementById('nd_fr')?.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено, группа ' + GROUP;
})();
// Чтение: (sessionStorage.getItem('nd_log15') || '') + '\n=====\n' + (sessionStorage.getItem('nd_day15') || '')
