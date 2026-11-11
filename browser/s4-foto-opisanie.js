// Правка созданного объявления на странице /items/edit/<id>: заменить фото на наш набор и добавить строку в описание.
// Запуск «выстрелил и забыл»: возвращает предыдущий журнал и «запущено»; журнал — sessionStorage.nd_log4.
// Меняются только ART (папка с фото в ветке paneli-render/avito_foto) и N (сколько фото).
const ART = 'A910', N = 7;
const LINE = 'Дизайнерам — бесплатно пришлём 3D-модели этого профиля и всего каталога (3ds Max, SketchUp, ArchiCAD, Revit, Blender). Напишите в чат.';
const prev = sessionStorage.getItem('nd_log4') || '';
sessionStorage.setItem('nd_log4', '');
const L = (...a) => { const s = new Date().toTimeString().slice(0, 8) + ' ' + a.join(' '); sessionStorage.setItem('nd_log4', (sessionStorage.getItem('nd_log4') || '') + s + '\n'); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  try {
    L('СТАРТ', ART, location.pathname);
    for (let i = 0; i < 30 && !document.querySelector('textarea[name=description]'); i++) await sleep(500);
    document.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
    const previews = () => [...document.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]')];
    const oldIds = previews().map(e => e.getAttribute('data-marker').match(/preview\((\d+)\)/)[1]);
    L('старых фото', oldIds.length);
    // 1. скачать наши фото
    const files = [];
    for (let i = 1; i <= N; i++) {
      const r = await fetch(`https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/paneli-render/avito_foto/${ART}/${i}.jpg`);
      if (!r.ok) throw new Error('фото ' + i + ' HTTP ' + r.status);
      files.push(new File([await r.blob()], `${ART}-${i}.jpg`, { type: 'image/jpeg' }));
    }
    L('скачано фото', files.length);
    // 2. загрузить
    const inp = document.querySelector('input[type=file][accept*="image"]');
    const dt = new DataTransfer();
    files.forEach(f => dt.items.add(f));
    inp.files = dt.files;
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    let ok = false;
    for (let i = 0; i < 90; i++) {
      await sleep(1000);
      const pv = previews();
      const loaded = pv.filter(e => /img\.avito\.st/.test(e.src || (e.querySelector('img') || {}).src || ''));
      if (pv.length >= oldIds.length + N && loaded.length >= oldIds.length + N) { ok = true; break; }
      if (i % 10 === 9) L('ждём загрузку', pv.length, 'загружено', loaded.length);
    }
    L('загрузка', ok ? 'ГОТОВО' : 'НЕ ДОЖДАЛИСЬ', 'превью', previews().length);
    if (!ok) { L('СТОП: фото не загрузились, сохранять не буду'); return; }
    // 3. удалить старые
    for (const id of oldIds) {
      const b = document.querySelector(`[data-marker="preview(${id})/delete-button"]`);
      if (b) { b.click(); await sleep(700); }
    }
    await sleep(800);
    const left = previews().map(e => e.getAttribute('data-marker').match(/preview\((\d+)\)/)[1]);
    L('после удаления фото', left.length, 'старые остались:', left.filter(x => oldIds.includes(x)).length);
    // 4. описание
    const ta = document.querySelector('textarea[name=description]');
    let v = ta.value;
    if (!v.includes(LINE)) {
      const m = v.match(/\n\n(Цена в объявлении[^\n]*)\s*$/);
      v = m ? v.slice(0, m.index) + '\n\n' + LINE + v.slice(m.index) : v.trimEnd() + '\n\n' + LINE;
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(ta, v);
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      ta.dispatchEvent(new Event('change', { bubbles: true }));
      ta.dispatchEvent(new Event('blur', { bubbles: true }));
    }
    await sleep(500);
    const ta2 = document.querySelector('textarea[name=description]');
    L('описание: строка есть', ta2.value.includes(LINE), 'длина', ta2.value.length);
    const nNew = left.filter(x => !oldIds.includes(x)).length;
    if (nNew !== N || left.length !== N || !ta2.value.includes(LINE)) { L('СТОП: проверка не прошла, сохранять не буду'); return; }
    // 5. сохранить
    const save = document.querySelector('[data-marker="item-edit/button-next"]');
    L('жму', (save && save.innerText || '').trim().split('\n')[0]);
    save.click();
    await sleep(6000);
    L('после сохранения', location.pathname + location.search, '|', (document.querySelector('h1,h2') || {}).innerText || '');
    const errs = [...document.querySelectorAll('[class*=error],[data-marker*=error]')].map(e => e.innerText.trim()).filter(Boolean).slice(0, 5);
    if (errs.length) L('ошибки на странице:', JSON.stringify(errs));
    L('ГОТОВО');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
'предыдущий журнал:\n' + prev + '\n— запущено ' + ART;
