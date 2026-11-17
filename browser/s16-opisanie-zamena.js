// Замена одной фразы в описаниях живых объявлений. 17.11.2026: материал называем «дюрополимер (ударопрочный полистирол)».
// JOBS: [артикул, номер, старая фраза, новая фраза]. Меняется только эта фраза и только если она стоит в описании ровно один раз;
// если её нет — объявление не сохраняется, в журнал пишутся строки со словами из WORDS, чтобы показать их Михаилу.
// READ — номера объявлений, которые только читаем (ищем слова из WORDS); PROFILE — страница профиля, тоже только чтение.
// WAIT15 = true — скрипт вставлен одним вызовом после s15-den.js: ждёт, пока обход закончится («ВСЁ» в nd_log15), и не правит,
// если обход не дошёл до конца или вход в кабинет не найден. Так обход и правка идут за один запуск и одно чтение.
// Всё во фрейме поверх страницы Авито, паузы через MessageChannel, запуск без await. Журнал — sessionStorage.nd_log16.
// После правки описания первый клик по «Сохранить изменения» только пересчитывает форму, сохраняет второй (проверено 12.11.2026).
(() => {
const A = 'Дюрополимер (плотный ударопрочный полистирол)', B = 'Дюрополимер (ударопрочный полистирол)';
const JOBS = [
  ['3-7', '8402676722', A, B],
  ['A910', '8523521242', A, B],
  ['A703', '8495178294', A, B],
  ['3-9', '8546190071', 'дюрополимер (ударопрочный полистирол высокой плотности)', 'дюрополимер (ударопрочный полистирол)'],
  ['3-15', '8530976650', 'ударопрочный полистирол высокой плотности (дюрополимер)', 'ударопрочный полистирол (дюрополимер)'],
];
const READ = ['8068817087'];
const PROFILE = '/brands/41c3cda03dbcc4779122153b28a75b36';
const WORDS = /плотн|кг\s*\/\s*м/i;
const WAIT15 = true;
const SS = sessionStorage; SS.setItem('nd_log16', '');
const L = (...a) => { SS.setItem('nd_log16', (SS.getItem('nd_log16') || '') + new Date().toTimeString().slice(0, 8) + ' ' + a.join(' ') + '\n'); };
const mc = new MessageChannel(); let wake = null;
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const until = async (cond, ms, step = 250) => { const t = Date.now() + ms; while (Date.now() < t) { let ok = false; try { ok = cond(); } catch (e) {} if (ok) return true; await sleep(step); } return false; };
const ta = d => d.querySelector('textarea[name=description]');
const titleInp = d => d.querySelector('input[name=title]') || d.querySelector('[data-marker*="title"] input');
const nPh = d => d.querySelectorAll('[data-marker^="preview("][data-marker$="/image"]').length;
const addr = d => (d.querySelector('input[name=address]') || {}).value || '?';
const hits = v => { const out = []; const re = new RegExp(WORDS.source, 'gi'); let m; while ((m = re.exec(v)) && out.length < 8) out.push('…' + v.slice(Math.max(0, m.index - 70), m.index + 80).replace(/\s+/g, ' ') + '…'); return out; };
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
async function job(art, id, a, b) {
  L('—', art, id);
  const fr = await frame('/items/edit/' + id, true);
  if (!fr) { L('СТОП', art, 'форма не открылась'); return false; }
  const d = fr.contentDocument, w = fr.contentWindow;
  d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));
  const t = ta(d), val = t.value, ph0 = nPh(d), ti0 = (titleInp(d) || {}).value, n = val.split(a).length - 1;
  if (n === 0 && val.includes(b)) { L(art, 'новая фраза уже стоит, не трогаю | ещё слова:', JSON.stringify(hits(val))); return true; }
  if (n !== 1) { L('СТОП', art, 'старая фраза встречается', n, 'раз — не трогаю. Строки со словами:', JSON.stringify(hits(val))); return false; }
  const nv = val.replace(a, b);
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
      const end = () => /(ВСЁ|ОШИБКА)\s*$/.test((SS.getItem('nd_log15') || '').trim());
      const ok = await until(end, 9 * 60000, 1500);
      const log15 = (SS.getItem('nd_log15') || '').trim(), day15 = SS.getItem('nd_day15') || '';
      if (!ok || !/ВСЁ\s*$/.test(log15)) { L('СТОП: обход s15 не дошёл до конца — описания не трогаю. Конец его журнала:', log15.slice(-200)); return; }
      if (/ВХОД:\s*НЕТ/i.test(day15)) { L('СТОП: обход шёл без входа в кабинет — описания не трогаю'); return; }
      L('обход закончен, начинаю правку описаний');
      await sleep(2500);
    }
    let stop = false;
    for (const j of JOBS) { const r = await job(...j); if (!r && /страница входа/.test(SS.getItem('nd_log16') || '')) { stop = true; break; } }
    if (!stop) {
      L('=== ПРОВЕРКА ===');
      for (const [art, id, a, b] of JOBS) {
        const fr = await frame('/items/edit/' + id, true);
        if (!fr) { L(art, 'проверка: не открылось'); continue; }
        const d = fr.contentDocument, v = ta(d).value;
        L(art, id, '| старая фраза:', v.includes(a) ? 'ЕСТЬ' : 'нет', '| новая:', v.includes(b) ? 'ЕСТЬ' : 'НЕТ', '| длина', v.length, '| заголовок: «' + (titleInp(d) || {}).value + '» | фото', nPh(d), '| адрес:', addr(d), '| ещё слова:', JSON.stringify(hits(v)));
      }
      for (const id of READ) {
        const fr = await frame('/items/edit/' + id, true);
        if (!fr) { L('ЧТЕНИЕ', id, 'не открылось'); continue; }
        const d = fr.contentDocument, v = ta(d).value, h = hits(v + '\n' + ((titleInp(d) || {}).value || ''));
        L('ЧТЕНИЕ', id, '| заголовок: «' + (titleInp(d) || {}).value + '» | длина описания', v.length, '| слова про плотность:', h.length ? JSON.stringify(h) : 'нет', '| про материал:', JSON.stringify((v.match(/[^\n.]*(дюрополимер|полистирол)[^\n.]*\.?/gi) || []).slice(0, 4)));
      }
      if (PROFILE) {
        const fr = await frame(PROFILE, false);
        if (!fr) L('ПРОФИЛЬ не открылся');
        else { const v = fr.contentDocument.body.innerText, h = hits(v); L('ПРОФИЛЬ', PROFILE, '| текста', v.length, 'зн. | слова про плотность:', h.length ? JSON.stringify(h) : 'нет', '| про материал:', JSON.stringify((v.match(/[^\n.]*(дюрополимер|полистирол)[^\n.]*\.?/gi) || []).slice(0, 4))); }
      }
    }
    document.getElementById('nd_fr')?.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
return 'запущено s16: ' + JOBS.map(j => j[0]).join(', ') + ' + чтение ' + READ.join(', ') + (WAIT15 ? ' (после обхода s15)' : '');
})();
// Чтение: (sessionStorage.getItem('nd_log15') || '') + '\n=====\n' + (sessionStorage.getItem('nd_day15') || '') + '\n===== s16\n' + (sessionStorage.getItem('nd_log16') || '')
