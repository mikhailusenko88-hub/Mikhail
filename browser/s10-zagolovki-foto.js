// Пакетная правка созданных объявлений за ОДНО подтверждение: новые заголовки и (по желанию) замена всех фото.
// Страницы редактирования открываются во фрейме поверх текущей страницы Авито. Журнал — sessionStorage.nd_log10.
// JOBS: [артикул, номер, папка фото в avito_foto/ или '', число фото, новый заголовок или '']
const JOBS = [
  ['A703', '8495178294', 'A703v3', 8, 'Плинтус напольный дюрополимер под покраску 80 мм'],
  ['3-7', '8402676722', '3-7v4', 8, 'Декоративные рейки на стену под дерево, дуб 3 м'],
  ['3-15', '8530976650', '3-15v4', 8, 'Стеновые панели рейки под светлое дерево, 3 м'],
  ['A910', '8523521242', 'A910v5', 9, 'Реечные панели из дюрополимера под покраску'],
  ['3-9', '8546190071', '3-9v4', 8, ''],
];
const RAW = 'https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/paneli-render/avito_foto/';
sessionStorage.setItem('nd_log10', '');
document.getElementById('nd_ov')?.remove();
const L = (...a) => { const s = new Date().toTimeString().slice(0, 8) + ' ' + a.join(' '); sessionStorage.setItem('nd_log10', (sessionStorage.getItem('nd_log10') || '') + s + '\n'); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function frame(url) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_fr';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#fff;border:0';
  fr.src = url; document.body.appendChild(fr);
  for (let i = 0; i < 60; i++) {
    await sleep(500);
    try { const d = fr.contentDocument; if (d && d.querySelector('textarea[name=description]')) { await sleep(1500); return fr; } }
    catch (e) { L('фрейм недоступен', e.message); return null; }
  }
  L('фрейм: форма не появилась'); return null;
}
const ids = d => [...d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]')].map(e => e.getAttribute('data-marker').match(/preview\((\d+)\)/)[1]);
const loadedN = d => [...d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]')].filter(e => /img\.avito\.st/.test(e.src || (e.querySelector('img') || {}).src || '')).length;
const titleInp = d => d.querySelector('input[name=title]') || d.querySelector('[data-marker*="title"] input') ||
  [...d.querySelectorAll('input[type=text],input:not([type])')].find(i => i.value && i.value.length > 15 && /панел|плинтус|рейк/i.test(i.value));
async function job(art, id, folder, N, title) {
  L('—', art, id);
  const fr = await frame('/items/edit/' + id);
  if (!fr) { L('СТОП', art, 'страница не открылась'); return false; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const ti = titleInp(d);
  if (!ti) { L('СТОП', art, 'поле заголовка не найдено'); return false; }
  L('заголовок был:', ti.value, '| поле', ti.name || ti.getAttribute('data-marker') || '?');
  const old = ids(d);
  if (folder) {
    const dt = new w.DataTransfer();
    for (let i = 1; i <= N; i++) {
      const r = await fetch(RAW + folder + '/' + i + '.jpg', { cache: 'no-store' });
      if (!r.ok) { L('СТОП', art, 'фото', i, 'HTTP', r.status); return false; }
      dt.items.add(new w.File([await r.blob()], art + '-' + i + '.jpg', { type: 'image/jpeg' }));
    }
    const inp = d.querySelector('input[type=file][accept*="image"]');
    inp.files = dt.files; inp.dispatchEvent(new w.Event('change', { bubbles: true }));
    let ok = false;
    for (let i = 0; i < 120; i++) { await sleep(1000); if (ids(d).length >= old.length + N && loadedN(d) >= old.length + N) { ok = true; break; } if (i % 15 === 14) L('ждём загрузку', ids(d).length); }
    if (!ok) { L('СТОП', art, 'фото не загрузились, не сохраняю'); return false; }
    for (const p of old) { const b = d.querySelector(`[data-marker="preview(${p})/delete-button"]`); if (b) { b.click(); await sleep(700); } }
    await sleep(800);
    const left = ids(d), nNew = left.filter(x => !old.includes(x)).length;
    L('фото', left.length, 'новых', nNew);
    if (nNew !== N || left.length !== N) { L('СТОП', art, 'фото не сходятся, не сохраняю'); return false; }
  }
  if (title) {
    const t2 = titleInp(d);
    Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype, 'value').set.call(t2, title);
    ['input', 'change', 'blur'].forEach(t => t2.dispatchEvent(new w.Event(t, { bubbles: true })));
    await sleep(900);
    if (titleInp(d).value !== title) { L('СТОП', art, 'заголовок не встал:', titleInp(d).value); return false; }
  }
  d.querySelector('[data-marker="item-edit/button-next"]').click();
  let path = '';
  for (let i = 0; i < 40; i++) { await sleep(500); try { path = w.location.pathname; } catch (e) { path = '?'; } if (!/\/items\/edit/.test(path)) break; }
  if (/\/items\/edit/.test(path)) {
    const errs = [...d.querySelectorAll('[class*=error],[data-marker*=error]')].map(e => e.innerText.trim()).filter(Boolean).slice(0, 5);
    L('СТОП', art, 'не сохранилось', JSON.stringify(errs)); return false;
  }
  L(art, 'СОХРАНЕНО →', path);
  return true;
}
(async () => {
  try {
    for (const j of JOBS) { await job(...j); }
    L('=== ПРОВЕРКА ===');
    for (const [a, id, folder, n, title] of JOBS) {
      const fr = await frame('/items/edit/' + id);
      if (!fr) { L(a, 'проверка: не открылось'); continue; }
      const d = fr.contentDocument;
      L(a, id, '| заголовок:', (titleInp(d) || {}).value, title && (titleInp(d) || {}).value === title ? 'ОК' : '', '| фото', ids(d).length, '| адрес:', (d.querySelector('input[name=address]') || {}).value || '?');
    }
    const fr = document.getElementById('nd_fr'); if (fr) fr.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
'запущено: ' + JOBS.map(j => j[0]).join(', ');
