// Оформление профиля (решения Михаила 11.11.2026): контактное лицо «Юлия», звонки 10:00–20:00,
// телефон Юлии в профиль, 8 фото 3D-интерьеров в «Фотографии», удалить сохранённый адрес с улицей.
// Всё во фрейме за пределами экрана; журнал — sessionStorage.nd_prof3. Запуск + чтение = 2 подтверждения.
const NAME = 'Юлия', FROM = '10:00', TO = '20:00', PHONE = '204-10-47';
const PHOTOS = ['3-7/1', 'A910/1', '3-9/1', '3-15/1', 'A910/2', '3-7/2', '3-15/3', 'A703/2'];
const RAW = 'https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/paneli-render/avito_foto/';
sessionStorage.setItem('nd_prof3', '');
const L = (...a) => sessionStorage.setItem('nd_prof3', (sessionStorage.getItem('nd_prof3') || '') + new Date().toTimeString().slice(0, 8) + ' ' + a.join(' ') + '\n');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const norm = s => (s || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').trim();
let fr;
const d = () => fr.contentDocument, w = () => fr.contentWindow;
const q = s => d().querySelector(s), qa = s => [...d().querySelectorAll(s)];
async function open(url, ready) {
  if (fr) fr.remove();
  fr = document.createElement('iframe');
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups');
  fr.style.cssText = 'position:fixed;left:-3000px;top:0;width:1280px;height:2400px';
  fr.src = url; document.body.appendChild(fr);
  for (let i = 0; i < 30; i++) { await sleep(500); try { if (ready.test(d().body.innerText)) break; } catch (e) {} }
  await sleep(2000);
}
const vis = e => e && e.getClientRects().length;
const leaf = (re, root) => [...(root || d()).querySelectorAll('body *, *')].filter(e => e.children.length === 0 && vis(e) && re.test(norm(e.textContent)));
const dialogs = () => qa('[role=dialog], [aria-modal=true], [data-marker*=modal], [class*=Modal-root], [class*=modal-root], [data-marker="portals-container"] > *').filter(e => vis(e) && norm(e.innerText) && !e.closest('[data-marker^="more-popup"],header,[data-marker^="header"]'));
const ctl = root => [...root.querySelectorAll('input, textarea, button, [role=button], [role=option], [role=radio], [role=checkbox], label, [data-marker]')].filter(vis).map(e => e.tagName + (e.type ? '[' + e.type + ']' : '') + (e.name ? ' n=' + e.name : '') + (e.checked ? ' ON' : '') + (e.getAttribute('data-marker') ? ' {' + e.getAttribute('data-marker') + '}' : '') + ':' + norm(e.innerText || e.value || '').replace(/\n+/g, '/').slice(0, 40)).filter(s => !/:$/.test(s) || /\{|n=/.test(s)).slice(0, 30).join(' ; ');
const setVal = (el, v) => { Object.getOwnPropertyDescriptor(w().HTMLInputElement.prototype, 'value').set.call(el, v); ['input', 'change'].forEach(t => el.dispatchEvent(new (w().Event)(t, { bubbles: true }))); };
async function pickTime(marker, val) {
  const t = q(`[data-marker="time/${marker}/select-text"]`);
  if (!t) { L('нет поля времени', marker); return; }
  let box = t; for (let k = 0; k < 4 && box && !/button|select/i.test((box.getAttribute('role') || '') + box.tagName); k++) box = box.parentElement;
  (box || t).click(); await sleep(1200);
  let opt = leaf(new RegExp('^' + val + '$')).filter(e => !e.closest(`[data-marker="time/${marker}/select-text"]`))[0];
  if (!opt) { const sel = (box || t).closest('div').querySelector('select'); if (sel) { const o = [...sel.options].find(o => norm(o.textContent) === val); if (o) { sel.value = o.value; sel.dispatchEvent(new (w().Event)('change', { bubbles: true })); L('время через select', marker, val); await sleep(800); return; } } }
  if (opt) { opt.click(); await sleep(1000); }
  L('время', marker, '→', norm(t.innerText), opt ? '' : '(вариант ' + val + ' не найден; видны: ' + leaf(/^\d\d:\d\d$/).slice(0, 6).map(e => e.textContent).join(',') + ')');
}
(async () => {
  try {
    // 1–2. Настройки: контактное лицо и время звонков
    await open('/profile/settings', /Контактное лицо/);
    const m = q('input[name=manager]');
    if (m && norm(m.value) !== NAME) {
      setVal(m, NAME); await sleep(400);
      const btn = m.form ? [...m.form.querySelectorAll('button')].find(b => norm(b.innerText) === 'Сохранить') : null;
      (btn || [...qa('button')].find(b => norm(b.innerText) === 'Сохранить')).click(); await sleep(2500);
    }
    L('контактное лицо:', m ? norm(q('input[name=manager]').value) : 'нет поля');
    const any = q('[data-marker="time/any/switcher/toggle"]');
    if (any && any.checked) { (q('[data-marker="time/any/switcher"]') || any).click(); await sleep(1500); }
    L('«в любое время»:', any ? q('[data-marker="time/any/switcher/toggle"]').checked : 'нет');
    await pickTime('from', FROM); await pickTime('to', TO);
    const saveT = [...qa('button')].filter(b => vis(b) && norm(b.innerText) === 'Сохранить');
    L('кнопок «Сохранить» на странице:', saveT.length);
    // 3–4. Профиль: телефон и фото
    await open('/profile/extended', /Для связи/);
    const addPh = q('[data-marker="empty-phones/open-add-phone"]');
    if (addPh) {
      addPh.click(); await sleep(2500);
      const num = leaf(new RegExp(PHONE))[0];
      let dl = dialogs()[0];
      if (!dl && num) { dl = num; for (let k = 0; k < 8 && dl.parentElement && !dl.querySelector('button'); k++) dl = dl.parentElement; dl = dl.parentElement || dl; }
      if (!dl) L('телефон: окна нет; поля tel:', qa('input[type=tel]').filter(vis).length, '| новое на странице:', ctl(d().body).slice(-400));
      L('окно телефона:', dl ? norm(dl.innerText).replace(/\n+/g, ' | ').slice(0, 300) : 'нет', '|', dl ? ctl(dl) : '');
      if (dl) {
        const opt = [...dl.querySelectorAll('label, [role=checkbox], [role=radio], input[type=checkbox], input[type=radio]')].find(e => (e.closest('label') || e).innerText.includes(PHONE));
        if (opt) { const inp = (opt.querySelector && opt.querySelector('input')) || opt; if (!inp.checked) { (opt.closest('label') || opt).click(); await sleep(800); } }
        const ok = [...dl.querySelectorAll('button')].find(b => /^(Сохранить|Добавить|Готово|Применить)$/.test(norm(b.innerText)));
        if (opt && ok) { ok.click(); await sleep(2500); L('телефон: выбрал и нажал', norm(ok.innerText)); } else L('телефон: СТОП — номер в окне не найден или нет кнопки, ничего не нажимал');
      }
    } else L('телефон: кнопки «Добавить» нет (уже есть номер?)');
    await open('/profile/extended', /Для связи/);
    const up = q('[data-marker="file-uploader/label"] input[type=file]') || q('[data-marker="file-uploader/label"]')?.parentElement?.querySelector('input[type=file]') || qa('input[type=file]')[0];
    if (!up) L('фото: нет поля загрузки');
    else {
      const dt = new (w().DataTransfer)();
      const hf = document.createElement('iframe'); hf.setAttribute('sandbox', 'allow-scripts allow-same-origin'); hf.style.cssText = 'position:fixed;left:-4000px;top:0;width:800px;height:600px';
      hf.src = '/items/edit/8523521242'; document.body.appendChild(hf);
      for (let i = 0; i < 30; i++) { await sleep(500); try { if (hf.contentDocument.querySelector('textarea[name=description]')) break; } catch (e) {} }
      const get = async u => { try { return await fetch(u); } catch (e) { return await hf.contentWindow.fetch(u); } };
      const gal0 = qa('img').filter(i => vis(i) && i.naturalWidth > 100).length;
      for (const p of PHOTOS) { const r = await get(RAW + p + '.jpg'); if (!r.ok) { L('фото', p, 'HTTP', r.status); continue; } dt.items.add(new (w().File)([await r.blob()], p.replace('/', '-') + '.jpg', { type: 'image/jpeg' })); }
      up.files = dt.files; up.dispatchEvent(new (w().Event)('change', { bubbles: true }));
      hf.remove();
      L('фото: отдал', dt.files.length, 'файлов, multiple=' + up.multiple, '| картинок до', gal0);
      for (let i = 0; i < 40; i++) { await sleep(1000); if (dialogs().length) break; }
      const dl = dialogs()[0];
      if (dl) {
        L('окно фото:', norm(dl.innerText).replace(/\n+/g, ' | ').slice(0, 300), '|', ctl(dl));
        for (let i = 0; i < 40; i++) { await sleep(1000); if (![...dl.querySelectorAll('[class*=spinner],[class*=loader],[class*=progress]')].filter(vis).length) break; }
        const ok = [...dl.querySelectorAll('button')].find(b => /^(Сохранить|Готово|Опубликовать|Добавить|Загрузить)$/.test(norm(b.innerText)) && !b.disabled);
        if (ok) { ok.click(); await sleep(4000); L('фото: нажал', norm(ok.innerText)); } else L('фото: в окне нет активной кнопки сохранения');
      } else { await sleep(8000); L('фото: окна нет; картинок стало', qa('img').filter(i => vis(i) && i.naturalWidth > 100).length, '| рядом с галереей:', ctl(q('[data-marker="gallery-title"]')?.parentElement?.parentElement || d().body).slice(0, 500)); }
    }
    // 5. Адреса: удалить сохранённый адрес с улицей (первый в списке)
    await open('/profile/address', /Адреса/);
    const item = qa('[data-marker^="address-list"]').find(e => /,/.test(e.innerText));
    if (item) {
      const del = q('[data-marker="address-list-item/delete/0"]');
      let b = del; while (b && !/BUTTON|A/.test(b.tagName) && b.parentElement && b.parentElement !== item) b = b.parentElement;
      (b || del).dispatchEvent(new (w().MouseEvent)('click', { bubbles: true })); await sleep(1800);
      const dl = dialogs()[0];
      L('окно удаления:', dl ? norm(dl.innerText).replace(/\n+/g, ' | ').slice(0, 200) : 'нет');
      const yes = dl && [...dl.querySelectorAll('button')].find(x => /^Удалить/.test(norm(x.innerText)));
      if (yes) { yes.click(); await sleep(2500); }
    }
    // 6. Проверка
    await open('/profile/address', /Адреса/);
    L('ПРОВЕРКА адреса:', norm(qa('[data-marker^="address-list"]').map(e => e.innerText).join(' / ')) || 'список пуст');
    await open('/profile/settings', /Контактное лицо/);
    L('ПРОВЕРКА настройки: имя', norm(q('input[name=manager]').value), '| любое время', q('[data-marker="time/any/switcher/toggle"]').checked, '| с', norm((q('[data-marker="time/from/select-text"]') || {}).innerText), '| до', norm((q('[data-marker="time/to/select-text"]') || {}).innerText));
    await open('/profile/extended', /Для связи/);
    const t = norm(d().body.innerText).replace(/\n+/g, ' | ');
    const k = t.indexOf('Фотографии'), k2 = t.indexOf('Для связи');
    L('ПРОВЕРКА профиль: фото-картинок', qa('img').filter(i => vis(i) && i.naturalWidth > 100 && !/avatar|Аватар/i.test(i.alt + i.className)).length, '|', t.slice(k, k + 120), '|', t.slice(k2, k2 + 200));
    fr.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 400)); }
})();
'оформление запущено';
