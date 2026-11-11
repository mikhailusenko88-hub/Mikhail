// Пакетная правка созданных объявлений за ОДНО подтверждение:
// страницы редактирования открываются во фрейме поверх текущей страницы Авито (тот же сайт),
// в каждой: загрузить наши фото, удалить старые, добавить строку в описание, сохранить.
// Потом проверка всех объявлений. Журнал — sessionStorage.nd_log5.
const JOBS = [['3-7', '8402676722', 7], ['3-15', '8530976650', 7], ['3-9', '8546190071', 7], ['A703', '8495178294', 5]];
const CHECK = [['A910', '8523521242', 7], ...JOBS];
const LINE = 'Дизайнерам — бесплатно пришлём 3D-модели этого профиля и всего каталога (3ds Max, SketchUp, ArchiCAD, Revit, Blender). Напишите в чат.';
const RAW = 'https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/paneli-render/avito_foto/';
sessionStorage.setItem('nd_log5', '');
const L = (...a) => { const s = new Date().toTimeString().slice(0, 8) + ' ' + a.join(' '); sessionStorage.setItem('nd_log5', (sessionStorage.getItem('nd_log5') || '') + s + '\n'); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function frame(url) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe');
  fr.id = 'nd_fr';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#fff;border:0';
  fr.src = url; document.body.appendChild(fr);
  for (let i = 0; i < 60; i++) {
    await sleep(500);
    try { const d = fr.contentDocument; if (d && d.querySelector('textarea[name=description]')) { await sleep(1500); return fr; } }
    catch (e) { L('фрейм недоступен', e.message); return null; }
  }
  L('фрейм: форма не появилась', (() => { try { return fr.contentWindow.location.pathname; } catch (e) { return '?'; } })());
  return null;
}
const ids = d => [...d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]')].map(e => e.getAttribute('data-marker').match(/preview\((\d+)\)/)[1]);
const loadedN = d => [...d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]')].filter(e => /img\.avito\.st/.test(e.src || (e.querySelector('img') || {}).src || '')).length;
async function job(art, id, N) {
  L('—', art, id);
  const fr = await frame('/items/edit/' + id);
  if (!fr) { L('СТОП', art, 'страница не открылась'); return false; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const old = ids(d);
  const ta0 = d.querySelector('textarea[name=description]');
  if (old.length === N && ta0.value.includes(LINE)) { L(art, 'уже сделано, пропускаю'); return true; }
  L('старых фото', old.length);
  const dt = new w.DataTransfer();
  for (let i = 1; i <= N; i++) {
    const r = await fetch(RAW + art + '/' + i + '.jpg');
    if (!r.ok) { L('СТОП', art, 'фото', i, 'HTTP', r.status); return false; }
    dt.items.add(new w.File([await r.blob()], art + '-' + i + '.jpg', { type: 'image/jpeg' }));
  }
  const inp = d.querySelector('input[type=file][accept*="image"]');
  inp.files = dt.files;
  inp.dispatchEvent(new w.Event('change', { bubbles: true }));
  let ok = false;
  for (let i = 0; i < 120; i++) {
    await sleep(1000);
    if (ids(d).length >= old.length + N && loadedN(d) >= old.length + N) { ok = true; break; }
    if (i % 15 === 14) L('ждём загрузку', ids(d).length, 'загружено', loadedN(d));
  }
  L('загрузка', ok ? 'ок' : 'НЕ ДОЖДАЛИСЬ', 'превью', ids(d).length);
  if (!ok) { L('СТОП', art, 'фото не загрузились, не сохраняю'); return false; }
  for (const p of old) { const b = d.querySelector(`[data-marker="preview(${p})/delete-button"]`); if (b) { b.click(); await sleep(700); } }
  await sleep(800);
  const left = ids(d);
  const ta = d.querySelector('textarea[name=description]');
  if (!ta.value.includes(LINE)) {
    let v = ta.value; const m = v.match(/\n\n(Цена в объявлении[^\n]*)\s*$/);
    v = m ? v.slice(0, m.index) + '\n\n' + LINE + v.slice(m.index) : v.trimEnd() + '\n\n' + LINE;
    Object.getOwnPropertyDescriptor(w.HTMLTextAreaElement.prototype, 'value').set.call(ta, v);
    ['input', 'change', 'blur'].forEach(t => ta.dispatchEvent(new w.Event(t, { bubbles: true })));
  }
  await sleep(600);
  const ta2 = d.querySelector('textarea[name=description]');
  const nNew = left.filter(x => !old.includes(x)).length;
  L('фото', left.length, 'новых', nNew, 'строка', ta2.value.includes(LINE));
  if (nNew !== N || left.length !== N || !ta2.value.includes(LINE)) { L('СТОП', art, 'проверка не прошла, не сохраняю'); return false; }
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
    for (const [a, id, n] of JOBS) { await job(a, id, n); }
    L('=== ПРОВЕРКА ===');
    for (const [a, id, n] of CHECK) {
      const fr = await frame('/items/edit/' + id);
      if (!fr) { L(a, 'проверка: не открылось'); continue; }
      const d = fr.contentDocument;
      const ta = d.querySelector('textarea[name=description]');
      const adr = (d.querySelector('input[name=address]') || {}).value || '?';
      L(a, id, 'фото', ids(d).length + '/' + n, '| строка', ta.value.includes(LINE), '| начало:', ta.value.slice(0, 40).replace(/\n/g, ' '), '| адрес:', adr);
    }
    const fr = document.getElementById('nd_fr'); if (fr) fr.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
'запущено пакетом: ' + JOBS.map(j => j[0]).join(', ');
