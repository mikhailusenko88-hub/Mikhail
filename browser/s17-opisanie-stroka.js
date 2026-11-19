// Строка в конец описания живого объявления (например «Также ищут: …» — короткий список фраз про сам товар).
// 19.11.2026: менеджер Авито посоветовала дописывать после основного текста слова и фразы, относящиеся к товару;
// правила Авито разрешают только слова про сам товар, длинные списки отклоняют — поэтому одна строка, около десяти фраз,
// и сначала на одном объявлении (3-9). Михаил сказал «да» 20.11.2026 в 01:08, текст строки ему показан.
// JOBS: [артикул, номер, строка]. Строка дописывается через пустую строку после текста; если она уже стоит — объявление не трогается;
// если в описании есть другая строка «Также ищут» — не трогается и пишется в журнал.
// WAIT15 = true — скрипт вставлен одним вызовом после s15-den.js: ждёт «ВСЁ» в nd_log15 и не правит, если обход не дошёл до конца,
// был блок или нет входа в кабинет. Всё во фрейме поверх страницы Авито, паузы через MessageChannel, запуск без await.
// Журнал — sessionStorage.nd_log17. После правки описания «Сохранить изменения» иногда срабатывает со второго клика — он в скрипте есть.
(() => {
const JOBS = [
  ['3-9', '8546190071', 'Также ищут: реечные панели под дерево, декоративные рейки на стену, рейки для стен, стеновые панели под дерево, панели для стен, реечная панель орех, рейки на стену под дерево, интерьерные рейки, отделка стен рейками, панели из дюрополимера.'],
];
const WAIT15 = true;
const SS = sessionStorage; SS.setItem('nd_log17', '');
const L = (...a) => { SS.setItem('nd_log17', (SS.getItem('nd_log17') || '') + new Date().toTimeString().slice(0, 8) + ' ' + a.join(' ') + '\n'); };
const mc = new MessageChannel(); let wake = null;
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const until = async (cond, ms, step = 250) => { const t = Date.now() + ms; while (Date.now() < t) { let ok = false; try { ok = cond(); } catch (e) {} if (ok) return true; await sleep(step); } return false; };
const ta = d => d.querySelector('textarea[name=description]');
const titleInp = d => d.querySelector('input[name=title]') || d.querySelector('[data-marker*="title"] input');
const nPh = d => d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]').length;
const addr = d => (d.querySelector('input[name=address]') || {}).value || '?';
async function frame(url, form) {
  let fr = document.getElementById('nd_fr'); if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_fr';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#fff;border:0';
  fr.src = url; document.body.appendChild(fr);
  const login = () => { try { return /login/.test(fr.contentWindow.location.hash + fr.contentWindow.location.pathname); } catch (e) { return false; } };
  const ready = () => { const d = fr.contentDocument; if (!d || d.readyState !== 'complete') return false; return form ? !!ta(d) : (d.body && d.body.innerText.length > 600); };
  await until(() => login() || ready(), form ? 60000 : 30000);
  if (login()) { L('фрейм', url, '— страница входа: в кабинет не вошли'); return null; }
  if (!ready()) { let t = ''; try { t = (fr.contentDocument.title || '') + ' | ' + (fr.contentDocument.body.innerText || '').slice(0, 160).replace(/\s+/g, ' '); } catch (e) { t = e.message; } L('фрейм', url, '— не открылось:', t); return null; }
  await sleep(form ? 2000 : 1200);
  return fr;
}
async function job(art, id, line) {
  L('—', art, id);
  const fr = await frame('/items/edit/' + id, true);
  if (!fr) { L('СТОП', art, 'форма не открылась'); return false; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const t = ta(d), val = t.value, ph0 = nPh(d), ti0 = (titleInp(d) || {}).value;
  if (val.includes(line)) { L(art, 'строка уже стоит, не трогаю | длина', val.length); return true; }
  const other = val.search(/Также ищут\s*:/i);
  if (other >= 0) { L('СТОП', art, 'в описании уже есть другая строка «Также ищут» — не трогаю:', val.slice(other, other + 200).replace(/\s+/g, ' ')); return false; }
  const nv = val.replace(/\s+$/, '') + '\n\n' + line;
  Object.getOwnPropertyDescriptor(w.HTMLTextAreaElement.prototype, 'value').set.call(t, nv);
  ['input', 'change', 'blur'].forEach(e => t.dispatchEvent(new w.Event(e, { bubbles: true })));
  await sleep(1000);
  const now = ta(d).value;
  if (now !== nv) { L('СТОП', art, 'описание не встало (длина', now.length, 'вместо', nv.length + ') — не сохраняю'); return false; }
  if (nPh(d) !== ph0 || (titleInp(d) || {}).value !== ti0) { L('СТОП', art, 'изменились фото или заголовок — не сохраняю'); return false; }
  const btn = d.querySelector('[data-marker="item-edit/button-next"]');
  if (!btn) { L('СТОП', art, 'нет кнопки «Сохранить»'); return false; }
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
  L(art, 'СОХРАНЕНО →', path, '| было', val.length, 'зн., стало', nv.length);
  await sleep(1500);
  return true;
}
(async () => {
  try {
    L('=== запуск ===', location.pathname);
    if (WAIT15) {
      const end = () => { const t = (SS.getItem('nd_log15') || '').trim(); return /ВСЁ$/.test(t) || /\d ОШИБКА/.test(t); };
      const ok = await until(end, 9 * 60000, 1500);
      const log15 = (SS.getItem('nd_log15') || '').trim(), day15 = SS.getItem('nd_day15') || '';
      if (!ok || !/ВСЁ$/.test(log15)) { L('СТОП: обход s15 не дошёл до конца — описание не трогаю. Конец его журнала:', log15.slice(-200)); return; }
      if (/БЛОК на/.test(log15) || /!! блок на|кабинет: блок|»: блок/.test(day15)) { L('СТОП: в обходе Авито показал блок — описание не трогаю'); return; }
      if (/ВХОД:\s*НЕТ/i.test(day15)) { L('СТОП: обход шёл без входа в кабинет — описание не трогаю'); return; }
      L('обход закончен, начинаю правку описания');
      await sleep(2500);
    }
    let stop = false;
    for (const j of JOBS) { const r = await job(...j); if (!r && /страница входа/.test(SS.getItem('nd_log17') || '')) { stop = true; break; } }
    if (!stop) {
      L('=== ПРОВЕРКА ===');
      for (const [art, id, line] of JOBS) {
        const fr = await frame('/items/edit/' + id, true);
        if (!fr) { L(art, 'проверка: не открылось'); continue; }
        const d = fr.contentDocument, v = ta(d).value;
        L(art, id, '| строка:', v.includes(line) ? 'ЕСТЬ' : 'НЕТ', '| в конце:', v.replace(/\s+$/, '').endsWith(line) ? 'да' : 'нет', '| длина', v.length, '| заголовок: «' + (titleInp(d) || {}).value + '» | фото', nPh(d), '| адрес:', addr(d), '| перед строкой: …' + v.replace(line, '').replace(/\s+$/, '').slice(-90).replace(/\s+/g, ' '));
      }
    }
    document.getElementById('nd_fr')?.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено s17: ' + JOBS.map(j => j[0]).join(', ') + (WAIT15 ? ' (после обхода s15)' : '');
})();
// Чтение: (sessionStorage.getItem('nd_log15') || '') + '\n=====\n' + (sessionStorage.getItem('nd_day15') || '') + '\n===== s17\n' + (sessionStorage.getItem('nd_log17') || '')
