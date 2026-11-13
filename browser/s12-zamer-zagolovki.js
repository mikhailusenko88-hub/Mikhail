// Замер и правка для поиска Авито за 2 подтверждения (запуск + чтение журнала). Навык avito-poisk-rost.
// Части включаются константами: JOBS — смена заголовков (может быть пустым), CAB — прочитать кабинет,
// QS — места наших объявлений по запросам (первая страница, 50 карточек; вторая — если на первой нас нет),
// TOP — у скольких первых карточек снять заголовок, цену, значки и продавца (0 — не снимать).
// Журнал — sessionStorage.nd_log12, карточки лидеров — sessionStorage.nd_top12. Собран 13.11.2026 из проверенных в тот день кусков.
// Вызов javascript_tool обрывается через 45 с — скрипт сразу возвращает «запущено», журнал читать отдельным вызовом через 1,5–2 минуты.
(() => {
const JOBS = [
  // ['3-7', '8402676722', 'Реечные панели под дерево дуб, рейки на стену 3 м'],
];
const CAB = true;
const QS = ['реечные панели под дерево', 'плинтус напольный под покраску', 'стеновые панели полистирол', 'реечные панели под покраску',
  'декоративные рейки на стену', 'панели дюрополимер', 'стеновые панели', 'плинтус дюрополимер'];
const TOP = 0;
const IDS = { '8402676722': '3-7', '8530976650': '3-15', '8546190071': '3-9', '8523521242': 'A910', '8495178294': 'A703', '8068817087': 'старое' };
const SS = sessionStorage; SS.setItem('nd_log12', ''); SS.setItem('nd_top12', '');
const L = (...a) => { SS.setItem('nd_log12', (SS.getItem('nd_log12') || '') + new Date().toTimeString().slice(0, 8) + ' ' + a.join(' ') + '\n'); };
const T = s => SS.setItem('nd_top12', (SS.getItem('nd_top12') || '') + s + '\n');
// паузы без setTimeout: при скрытой панели браузера таймеры срабатывают раз в минуту
const mc = new MessageChannel(); let wake = null;
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const until = async (cond, ms, step = 250) => { const t = Date.now() + ms; while (Date.now() < t) { let ok = false; try { ok = cond(); } catch (e) {} if (ok) return true; await sleep(step); } return false; };
function mk(url, hidden) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_fr';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:1366px;height:900px;z-index:2147483647;background:#fff;border:0' + (hidden ? ';opacity:0.02;pointer-events:none' : '');
  fr.src = url; document.body.appendChild(fr); return fr;
}
const blocked = d => { try { const t = (d.title || '') + ' ' + ((d.body && d.body.innerText) || '').slice(0, 300); return /Доступ ограничен|проблема с IP|не робот/i.test(t) ? t.replace(/\s+/g, ' ').slice(0, 120) : ''; } catch (e) { return ''; } };
const nPh = d => d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]').length;
const titleInp = d => d.querySelector('input[name=title]') || d.querySelector('[data-marker*="title"] input');
const ta = d => d.querySelector('textarea[name=description]');
async function edit(id) {
  const fr = mk('/items/edit/' + id, false);
  const ok = await until(() => fr.contentDocument && ta(fr.contentDocument) && fr.contentDocument.readyState === 'complete', 60000);
  if (!ok) return null;
  await sleep(1800); return fr;
}
async function job(art, id, title) {
  const fr = await edit(id);
  if (!fr) { L('СТОП', art, 'страница не открылась'); return; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const ti = titleInp(d), old = ti.value, ph0 = nPh(d), de0 = ta(d).value;
  if (old === title) { L(art, 'заголовок уже такой'); return; }
  if (title.length > 50) { L('СТОП', art, 'заголовок длиннее 50 знаков:', title.length); return; }
  Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype, 'value').set.call(ti, title);
  ['input', 'change', 'blur'].forEach(e => ti.dispatchEvent(new w.Event(e, { bubbles: true })));
  await sleep(1500);
  if (titleInp(d).value !== title) { L('СТОП', art, 'заголовок не встал:', titleInp(d).value); return; }
  if (nPh(d) !== ph0 || ta(d).value !== de0) { L('СТОП', art, 'изменились фото или описание — не сохраняю'); return; }
  let path = '';
  const gone = () => { try { path = w.location.pathname; } catch (e) { path = '?'; } return !/\/items\/edit/.test(path); };
  const btn = d.querySelector('[data-marker="item-edit/button-next"]');
  btn.click();
  let clicks = 1;
  if (!(await until(gone, 5000, 300))) {   // после правки описания сохраняет только второй клик; заголовку хватает одного
    const b2 = d.querySelector('[data-marker="item-edit/button-next"]') || btn, r = b2.getBoundingClientRect(), o = { bubbles: true, cancelable: true, view: w, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup'].forEach(e => b2.dispatchEvent(new (e.startsWith('pointer') ? w.PointerEvent : w.MouseEvent)(e, o)));
    b2.click(); clicks = 2;
    await until(gone, 30000, 300);
  }
  if (/\/items\/edit/.test(path)) { L('СТОП', art, 'страница не ушла после двух кликов'); return; }
  L(art, 'СОХРАНЕНО (кликов ' + clicks + ') →', path, '| было «' + old + '»');
  await sleep(1200);
}
async function cabinet() {
  const fr = mk('/profile', true);
  const ok = await until(() => fr.contentDocument && Object.keys(IDS).filter(id => fr.contentDocument.querySelector('a[href*="' + id + '"]')).length >= 4, 30000);
  await sleep(2500);
  const d = fr.contentDocument;
  if (blocked(d)) { L('кабинет: блок', blocked(d)); return; }
  L('кабинет загружен:', ok, '| вкладки:', JSON.stringify([...d.querySelectorAll('[data-marker*="tab"],[role=tab]')].map(e => (e.innerText || '').trim().replace(/\s+/g, ' ')).filter(x => x && x.length < 40).slice(0, 12)));
  L('кошелёк:', (((d.body.innerText || '').match(/Кошел[её]к[^₽]{0,60}₽/) || [''])[0].replace(/\s+/g, ' ')) || 'не видно');
  for (const id of Object.keys(IDS)) {
    const a = d.querySelector('a[href*="' + id + '"]');
    if (!a) { L(IDS[id], id, 'в списке нет'); continue; }
    let e = a, txt = '';
    for (let i = 0; i < 10 && e.parentElement; i++) { e = e.parentElement; txt = (e.innerText || '').trim(); if (txt.length > 160) break; }
    L(IDS[id], id, '|', txt.replace(/\s+/g, ' ').slice(0, 420));   // числа в строке: просмотры[+сегодня] контакты избранное
  }
}
async function serp(q, p) {
  const fr = mk('/sankt-peterburg?q=' + encodeURIComponent(q) + (p > 1 ? '&p=' + p : ''), true);
  await until(() => { const dd = fr.contentDocument; return dd && (dd.querySelectorAll('[data-marker="item"]').length >= 30 || blocked(dd)); }, 20000);
  await sleep(1000);
  const d = fr.contentDocument, b = blocked(d);
  if (b) { L('«' + q + '» стр.', p, 'БЛОК:', b); return null; }
  const cards = [...d.querySelectorAll('[data-marker="item"]')];   // считать ВСЕ карточки страницы, а не блок catalog-serp (в нём только первые 10)
  const idOf = c => (c.getAttribute('data-item-id') || c.id || '').replace(/\D/g, '');
  const ours = cards.map((c, i) => [idOf(c), i + 1]).filter(x => IDS[x[0]]).map(x => IDS[x[0]] + ' №' + ((p - 1) * 50 + x[1]));
  const promo = cards.slice(0, 10).filter(c => /Продвинуто/.test(c.innerText || '')).length;
  L('«' + q + '» стр.', p, '| всего', (((d.querySelector('[data-marker="page-title/count"]') || {}).innerText || '').trim()), '| карточек', cards.length, '| НАШИ:', ours.length ? ours.join(', ') : 'нет', '| «Продвинуто» в первой десятке:', promo);
  if (TOP && p === 1) {
    T('## ' + q);
    cards.slice(0, TOP).forEach((c, i) => {
      const t = ((c.querySelector('[itemprop="name"],[data-marker="item-title"]') || {}).innerText || '').trim();
      const pe = c.querySelector('[itemprop="price"]'), pr = pe ? (pe.getAttribute('content') || '') : '';
      const full = (c.innerText || '').replace(/\s+/g, ' '), fl = [];
      if (/Продвинуто/.test(full)) fl.push('ПРОДВИНУТО');
      if (/Доставка от|Только доставка/.test(full)) fl.push('доставка');
      if (/Оплата частями/.test(full)) fl.push('частями');
      const m = full.match(/−\d+%/); if (m) fl.push('скидка ' + m[0]);
      if (/на возврат/.test(full)) fl.push('возврат');
      const seller = (full.match(/(?:\.\.\. |Продвинуто |похожее у продавца |назад |Вчера |Сегодня )?([^.]{2,60}?) (\d,\d · \d+ отзыв\S*|\d+ завершённ\S+ объявлени\S+|Нет завершённых объявлений)/) || []).slice(1, 3).join(' — ');
      T((i + 1) + '. ' + (IDS[idOf(c)] ? '[НАШЕ] ' : '') + t.slice(0, 50) + ' | ' + pr + ' | ' + fl.join(',') + ' | ' + seller.slice(-90));
    });
  }
  return ours.length;
}
(async () => {
  try {
    for (const j of JOBS) { await job(...j); }
    if (JOBS.length) {
      L('=== ПРОВЕРКА ===');
      for (const [a, id, title] of JOBS) {
        const fr = await edit(id);
        if (!fr) { L(a, 'проверка: не открылось'); continue; }
        const d = fr.contentDocument, tv = titleInp(d).value;
        L(a, '| заголовок: «' + tv + '»', tv === title ? 'ОК' : 'НЕ ТОТ', '| фото', nPh(d), '| описание', ta(d).value.length, 'зн. | адрес:', (d.querySelector('input[name=address]') || {}).value || '?');
      }
    }
    if (CAB) { L('=== КАБИНЕТ ==='); await cabinet(); }
    if (QS.length) L('=== ВЫДАЧА ===');
    for (const q of QS) {
      const n = await serp(q, 1);
      if (n === null) { L('поиск остановлен из-за блока'); break; }
      await sleep(1300 + Math.random() * 1000);
      if (n === 0) { const n2 = await serp(q, 2); if (n2 === null) break; await sleep(1300 + Math.random() * 1000); }
    }
    document.getElementById('nd_fr')?.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено';
})();
// Чтение: (sessionStorage.getItem('nd_log12') || '') + '\n=====\n' + (sessionStorage.getItem('nd_top12') || '')
