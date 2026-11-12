// Поисковые фразы в описания: в каждое объявление вторым абзацем вставляется одно предложение. Плюс чтение (без правки) ещё одного объявления.
// Всё во фрейме поверх любой страницы Авито, паузы через MessageChannel. Журнал — sessionStorage.nd_log11, сохранённые — nd_done11.
// JOBS: [артикул, номер, предложение]; READ — номера объявлений, которые только прочитать (заголовок, цена, фото, описание).
// 12.11.2026: так внесены предложения во все пять объявлений; старое объявление 8068817087 правилось тем же приёмом
// (заголовок «Декоративные стеновые панели из дюрополимера» + предложение «В каталоге: …» вторым абзацем; цена, фото, автопубликация не менялись).
// Важно: javascript_tool обрывается через 45 с — скрипт запускать без await и читать журнал отдельным вызовом.
(() => {
const JOBS = [
  ['3-7', '8402676722', 'Это декоративные рейки на стену — стеновые панели под дерево (дуб) для акцентной стены, изголовья кровати, прихожей, ниши.'],
  ['3-15', '8530976650', 'Это стеновые панели под светлое дерево — декоративные рейки на стену для акцентной стены, детской, прихожей, изголовья кровати.'],
  ['3-9', '8546190071', 'Это декоративные рейки на стену — стеновые панели под тёмное дерево (орех) для ТВ-зоны, акцентной стены, кабинета, ниши.'],
  ['A910', '8523521242', 'Белые стеновые панели под покраску: декоративные рейки на стену с рельефом «волна», реечные панели из дюрополимера.'],
  ['A703', '8495178294', 'Белый высокий плинтус 80 мм из дюрополимера под покраску — напольный, с каналом для кабеля.'],
];
const READ = [];   // номера только для чтения, например ['8068817087']
const SS = sessionStorage;
const L = (...a) => { const s = new Date().toTimeString().slice(0, 8) + ' ' + a.join(' '); SS.setItem('nd_log11', (SS.getItem('nd_log11') || '') + s + '\n'); };
const done = () => (SS.getItem('nd_done11') || '').split(',').filter(Boolean);
const mc = new MessageChannel(); let wake = null;
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const until = async (cond, ms, step = 250) => { const t = Date.now() + ms; while (Date.now() < t) { let ok = false; try { ok = cond(); } catch (e) {} if (ok) return true; await sleep(step); } return false; };
async function frame(url) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_fr';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#fff;border:0';
  fr.src = url; document.body.appendChild(fr);
  const ok = await until(() => fr.contentDocument && fr.contentDocument.querySelector('textarea[name=description]') && fr.contentDocument.readyState === 'complete', 60000);
  if (!ok) { let t = ''; try { t = (fr.contentDocument.title || '') + ' | ' + (fr.contentDocument.body.innerText || '').slice(0, 160).replace(/\s+/g, ' '); } catch (e) { t = e.message; } L('фрейм: форма не появилась:', t); return null; }
  await sleep(2000);
  return fr;
}
const nPh = d => d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]').length;
const titleInp = d => d.querySelector('input[name=title]') || d.querySelector('[data-marker*="title"] input');
const ta = d => d.querySelector('textarea[name=description]');
async function job(art, id, sent) {
  if (done().includes(art)) { L('—', art, 'уже сохранено раньше, пропускаю'); return true; }
  L('—', art, id);
  const fr = await frame('/items/edit/' + id);
  if (!fr) { L('СТОП', art, 'страница не открылась'); return false; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const t = ta(d), val = t.value, ph0 = nPh(d), ti0 = (titleInp(d) || {}).value;
  if (val.includes(sent)) { L(art, 'предложение уже есть, не трогаю'); SS.setItem('nd_done11', done().concat(art).join(',')); return true; }
  const paras = val.split(/\n\s*\n/);
  if (paras.length < 3) { L('СТОП', art, 'описание не похоже на ожидаемое, абзацев', paras.length, '— не трогаю:', val.slice(0, 200)); return false; }
  const k = (/^\s*Под заказ/i.test(paras[0]) && !/\n/.test(paras[0].trim())) ? 1 : 0;
  paras.splice(k + 1, 0, sent);
  const nv = paras.join('\n\n');
  L('было', val.length, 'зн., начало:', JSON.stringify(val.slice(0, 230)));
  Object.getOwnPropertyDescriptor(w.HTMLTextAreaElement.prototype, 'value').set.call(t, nv);
  ['input', 'change', 'blur'].forEach(e => t.dispatchEvent(new w.Event(e, { bubbles: true })));
  await sleep(1000);
  const now = ta(d).value;
  if (now !== nv) { L('СТОП', art, 'описание не встало (длина', now.length, 'вместо', nv.length + ') — не сохраняю'); return false; }
  if (nPh(d) !== ph0 || (titleInp(d) || {}).value !== ti0) { L('СТОП', art, 'изменились фото или заголовок — не сохраняю'); return false; }
  const btn = d.querySelector('[data-marker="item-edit/button-next"]');
  if (!btn) { L('СТОП', art, 'нет кнопки «Сохранить»'); return false; }
  // После правки описания первый клик только пересчитывает форму (layout + estimate), сохраняет второй клик (проверено 12.11.2026).
  let path = '';
  const gone = () => { try { path = w.location.pathname; } catch (e) { path = '?'; } return !/\/items\/edit/.test(path); };
  btn.click();
  if (!(await until(gone, 5000, 300))) {
    const b2 = d.querySelector('[data-marker="item-edit/button-next"]') || btn, r = b2.getBoundingClientRect(), o = { bubbles: true, cancelable: true, view: w, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup'].forEach(e => b2.dispatchEvent(new (e.startsWith('pointer') ? w.PointerEvent : w.MouseEvent)(e, o)));
    b2.click();
    L(art, 'второй клик по «Сохранить»');
    await until(gone, 30000, 300);
  }
  if (/\/items\/edit/.test(path)) {
    const errs = [...d.querySelectorAll('[class*=error],[data-marker*=error],[role=dialog],[aria-modal=true]')].map(e => (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 140)).filter(Boolean).slice(0, 6);
    L('СТОП', art, 'страница не ушла после «Сохранить»', JSON.stringify(errs)); return false;
  }
  SS.setItem('nd_done11', done().concat(art).join(','));
  L(art, 'СОХРАНЕНО →', path, '| стало', nv.length, 'зн.');
  await sleep(1500);
  return true;
}
(async () => {
  try {
    L('=== запуск ===', location.pathname);
    for (const j of JOBS) { await job(...j); }
    L('=== ПРОВЕРКА ===');
    for (const [a, id, sent] of JOBS) {
      const fr = await frame('/items/edit/' + id);
      if (!fr) { L(a, 'проверка: не открылось'); continue; }
      const d = fr.contentDocument, v = ta(d).value, i = v.indexOf(sent);
      L(a, id, '| предложение', i >= 0 ? 'ЕСТЬ, позиция ' + i : 'НЕТ', '| длина', v.length, '| заголовок: «' + (titleInp(d) || {}).value + '» | фото', nPh(d), '| адрес:', (d.querySelector('input[name=address]') || {}).value || '?', '| начало:', JSON.stringify(v.slice(0, 120)));
    }
    for (const id of READ) {
      const fr = await frame('/items/edit/' + id);
      if (!fr) { L('ЧТЕНИЕ', id, 'не открылось'); continue; }
      const d = fr.contentDocument;
      const price = (d.querySelector('input[name=price]') || {}).value || [...d.querySelectorAll('input')].filter(i => /price/i.test(i.name || '') || /price/i.test(i.getAttribute('data-marker') || '')).map(i => i.value).join('/');
      const sel = [...d.querySelectorAll('input[type=checkbox],input[type=radio]')].filter(c => c.checked).map(c => (c.name || c.getAttribute('data-marker') || '?') + '=' + c.value).join(', ');
      L('ЧТЕНИЕ', id, '| заголовок: «' + (titleInp(d) || {}).value + '» | цена:', price, '| фото', nPh(d), '| адрес:', (d.querySelector('input[name=address]') || {}).value || '?', '| выбрано:', sel, '\nОПИСАНИЕ:\n' + ta(d).value);
    }
    const fr = document.getElementById('nd_fr'); if (fr) fr.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено: ' + JOBS.map(j => j[0]).join(', ') + ' + чтение ' + READ.join(', ');
})();
