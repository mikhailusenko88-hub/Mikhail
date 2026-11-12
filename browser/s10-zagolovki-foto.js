// Пакетная правка созданных объявлений за ОДНО подтверждение: замена всех фото и новые заголовки.
// Страницы редактирования открываются во фрейме поверх текущей страницы Авито. Журнал — sessionStorage.nd_log10.
// Паузы — через MessageChannel (таймеры страницы при скрытой панели браузера срабатывают раз в минуту).
// Порядок на объявление: скачать новые фото → удалить старые → загрузить новые → заголовок → сохранить. Любое расхождение — СТОП без сохранения.
// JOBS: [артикул, номер, папка фото в avito_foto/ или '', число фото, новый заголовок или '']
(() => {
const JOBS = [
  ['A703', '8495178294', 'A703v3', 8, 'Плинтус напольный дюрополимер под покраску 80 мм'],
  ['3-7', '8402676722', '3-7v4', 8, 'Декоративные рейки на стену под дерево, дуб 3 м'],
  ['3-15', '8530976650', '3-15v4', 8, 'Стеновые панели рейки под светлое дерево, 3 м'],
  ['A910', '8523521242', 'A910v5', 8, 'Реечные панели из дюрополимера под покраску'],
  ['3-9', '8546190071', '3-9v4', 8, ''],
];
const RAW = 'https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/paneli-render/avito_foto/';
const SS = sessionStorage;
document.getElementById('nd_ov')?.remove();
const L = (...a) => { const s = new Date().toTimeString().slice(0, 8) + ' ' + a.join(' '); SS.setItem('nd_log10', (SS.getItem('nd_log10') || '') + s + '\n'); };
const done = () => (SS.getItem('nd_done10') || '').split(',').filter(Boolean);
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
const pv = d => [...d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]')];
const ids = d => pv(d).map(e => (e.getAttribute('data-marker').match(/preview\(([^)]+)\)/) || [])[1]).filter(Boolean);
const loadedN = d => pv(d).filter(e => /img\.avito\.st/.test(e.src || (e.querySelector('img') || {}).src || '')).length;
const titleInp = d => d.querySelector('input[name=title]') || d.querySelector('[data-marker*="title"] input') ||
  [...d.querySelectorAll('input[type=text],input:not([type])')].find(i => i.value && i.value.length > 15 && /панел|плинтус|рейк/i.test(i.value));
const checks = d => [...d.querySelectorAll('input[type=checkbox]')].filter(c => c.checked).map(c => c.name || c.getAttribute('data-marker') || '?').join(',');
async function job(art, id, folder, N, title) {
  if (done().includes(art)) { L('—', art, 'уже сохранено раньше, пропускаю'); return true; }
  L('—', art, id);
  const fr = await frame('/items/edit/' + id);
  if (!fr) { L('СТОП', art, 'страница не открылась'); return false; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const ti = titleInp(d);
  if (!ti) { L('СТОП', art, 'поле заголовка не найдено'); return false; }
  const old = ids(d);
  L('было: заголовок «' + ti.value + '» | фото', old.length, '| адрес:', (d.querySelector('input[name=address]') || {}).value || '?', '| отмечено:', checks(d));
  if (folder) {
    const files = [];
    for (let i = 1; i <= N; i++) {
      const u = RAW + folder + '/' + i + '.jpg';
      let r; try { r = await w.fetch(u, { cache: 'no-store' }); } catch (e) { try { r = await fetch(u, { cache: 'no-store' }); } catch (e2) { L('СТОП', art, 'фото', i, 'не скачалось:', e2.message); return false; } }
      if (!r.ok) { L('СТОП', art, 'фото', i, 'HTTP', r.status); return false; }
      const b = await r.blob();
      if (b.size < 50000) { L('СТОП', art, 'фото', i, 'слишком маленькое:', b.size); return false; }
      files.push(new w.File([b], art + '-' + i + '.jpg', { type: 'image/jpeg' }));
    }
    L('скачано', files.length, 'фото,', Math.round(files.reduce((s, f) => s + f.size, 0) / 1024), 'КБ');
    for (const p of old) {
      const b = d.querySelector(`[data-marker="preview(${p})/delete-button"]`);
      if (!b) { L('СТОП', art, 'нет кнопки удаления у фото', p, '— не сохраняю'); return false; }
      b.click();
      await until(() => !ids(d).includes(p), 8000, 150);
    }
    if (!(await until(() => ids(d).length === 0, 8000))) { L('СТОП', art, 'старые фото не удалились, осталось', ids(d).length, '— не сохраняю'); return false; }
    const inp = d.querySelector('input[type=file][accept*="image"]');
    if (!inp) { L('СТОП', art, 'нет поля загрузки фото — не сохраняю'); return false; }
    const dt = new w.DataTransfer(); files.forEach(f => dt.items.add(f));
    inp.files = dt.files; inp.dispatchEvent(new w.Event('change', { bubbles: true }));
    const t0 = Date.now(); let lastLog = 0;
    const ok = await until(() => { if (Date.now() - lastLog > 20000) { lastLog = Date.now(); L('загрузка: превью', ids(d).length, 'готово', loadedN(d)); } return ids(d).length === N && loadedN(d) === N; }, 240000, 500);
    if (!ok) { L('СТОП', art, 'фото не загрузились: превью', ids(d).length, 'готово', loadedN(d), '— не сохраняю'); return false; }
    await sleep(1200);
    const left = ids(d), stale = left.filter(x => old.includes(x)).length;
    L('фото загружены за', Math.round((Date.now() - t0) / 1000), 'с: всего', left.length, 'старых', stale);
    if (left.length !== N || stale) { L('СТОП', art, 'фото не сходятся — не сохраняю'); return false; }
  }
  if (title) {
    const t2 = titleInp(d);
    Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype, 'value').set.call(t2, title);
    ['input', 'change', 'blur'].forEach(t => t2.dispatchEvent(new w.Event(t, { bubbles: true })));
    await sleep(1000);
    if (titleInp(d).value !== title) { L('СТОП', art, 'заголовок не встал:', titleInp(d).value, '— не сохраняю'); return false; }
  }
  const btn = d.querySelector('[data-marker="item-edit/button-next"]');
  if (!btn) { L('СТОП', art, 'нет кнопки «Сохранить»'); return false; }
  L('жму:', (btn.innerText || '').trim().replace(/\s+/g, ' '));
  btn.click();
  let path = '';
  await until(() => { try { path = w.location.pathname; } catch (e) { path = '?'; } return !/\/items\/edit/.test(path); }, 60000, 300);
  if (/\/items\/edit/.test(path)) {
    const errs = [...d.querySelectorAll('[class*=error],[data-marker*=error],[role=dialog],[aria-modal=true]')].map(e => (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 140)).filter(Boolean).slice(0, 6);
    L('СТОП', art, 'страница не ушла после «Сохранить»', JSON.stringify(errs)); return false;
  }
  SS.setItem('nd_done10', done().concat(art).join(','));
  L(art, 'СОХРАНЕНО →', path);
  await sleep(1500);
  return true;
}
(async () => {
  try {
    L('=== запуск ===', location.pathname);
    for (const j of JOBS) { await job(...j); }
    L('=== ПРОВЕРКА ===');
    for (const [a, id, folder, n, title] of JOBS) {
      const fr = await frame('/items/edit/' + id);
      if (!fr) { L(a, 'проверка: не открылось'); continue; }
      const d = fr.contentDocument, tv = (titleInp(d) || {}).value;
      L(a, id, '| заголовок: «' + tv + '»', title ? (tv === title ? 'ОК' : 'НЕ ТОТ') : '(не меняли)', '| фото', ids(d).length, ids(d).length === n ? 'ОК' : 'НЕ ' + n, '| адрес:', (d.querySelector('input[name=address]') || {}).value || '?', '| отмечено:', checks(d));
    }
    const fr = document.getElementById('nd_fr'); if (fr) fr.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено: ' + JOBS.map(j => j[0]).join(', ');
})();
