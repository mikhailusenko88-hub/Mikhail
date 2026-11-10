const AD = JSON.parse(sessionStorage.getItem('nd_ad') || 'null');
const log = JSON.parse(sessionStorage.getItem('nd_log') || '[]'); log.push('— скрипт 2 —');
const L = x => { log.push(x); sessionStorage.setItem('nd_log', JSON.stringify(log)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
const fire = (el, x, y) => { const r = el.getBoundingClientRect(); const o = {bubbles: true, cancelable: true, view: window, clientX: x ?? (r.x + Math.min(r.width / 2, 40)), clientY: y ?? (r.y + r.height / 2), button: 0, pointerId: 1, pointerType: 'mouse', isPrimary: true};
  for (const t of ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o)); };
const waitFor = async (fn, ms = 4000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = fn(); if (v) return v; await sleep(250); } return null; };
const setVal = (el, v) => { const p = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; el.focus(); Object.getOwnPropertyDescriptor(p, 'value').set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); };
const M = () => document.querySelector('main') || document.body;
const q = s => M().querySelector(s), qa = s => [...M().querySelectorAll(s)];
const hv = n => (q('input[name="' + n + '"]') || {}).value;
const AI = () => q('input[name="params[2855]"]'), TA = () => q('textarea[name=description]');
const CITY = 'Санкт-Петербург';
try {
if (!AD || !TA()) throw 'нет данных объявления (скрипт 1) или формы';
document.querySelectorAll('form').forEach(f => { if (!f.__nd) { f.__nd = 1; f.addEventListener('submit', e => e.preventDefault(), {capture: true}); } });
const addrOk = () => hv('address') === CITY && !!hv('coords[lat]') && (AI() || {}).value === CITY;
L('фокус=' + document.hasFocus() + ' поле=«' + ((AI() || {}).value || '') + '»');
for (const i of qa('input[type=text], textarea')) if (i !== AI() && (i.value || '') === CITY.slice(0, -1)) { L('текст попал в чужое поле ' + (i.name || '?') + ' — стираю'); setVal(i, ''); }
const cands = () => { const b = AI().getBoundingClientRect(); return [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && e.textContent.trim() === CITY && e !== AI() && e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().top > b.bottom && e.getBoundingClientRect().top < b.bottom + 160).sort((a, b2) => a.getBoundingClientRect().top - b2.getBoundingClientRect().top); };
const hit = s => { const row = s.closest('[role=option], li') || s.parentElement; const r = row.getBoundingClientRect(), sr = s.getBoundingClientRect(); const x = Math.min(Math.max(r.left + 40, 12), Math.min(r.right, innerWidth) - 12), y = sr.top + sr.height / 2; const t = document.elementFromPoint(x, y); return {row, x, y, t, ok: !!t && row.contains(t) && vis(s)}; };
if (!addrOk()) {
  AI().scrollIntoView({block: 'center'});
  await waitFor(() => cands().some(s => hit(s).ok), 5000);
  for (const mode of ['point', 'keys']) {
    if (addrOk()) break;
    const s = cands().find(x => hit(x).ok); if (!s) { L('подсказки «' + CITY + '» под полем нет (' + mode + ')'); break; }
    const h = hit(s);
    if (mode === 'point') fire(h.t, h.x, h.y);
    else for (const [k, code] of [['ArrowDown', 40], ['Enter', 13]]) { for (const ev of ['keydown', 'keyup']) AI().dispatchEvent(new KeyboardEvent(ev, {key: k, code: k, keyCode: code, which: code, bubbles: true, cancelable: true})); await sleep(300); }
    await sleep(1600);
    const v = (AI() || {}).value || '';
    if (v !== CITY && !CITY.startsWith(v)) { L('в поле «' + v.slice(0, 50) + '» — стираю'); setVal(AI(), ''); break; }
    L('адрес после ' + mode + ': ' + (addrOk() ? 'принят' : 'не принят'));
  }
  if (!addrOk()) { const s = cands().find(x => hit(x).ok); if (s) { const h = hit(s); L('НАСТОЯЩИЙ КЛИК в ' + Math.round(h.x * 800 / innerWidth) + ',' + Math.round(h.y * 1266 / innerHeight) + ', потом этот скрипт ещё раз'); } }
}
if (addrOk()) {
  const rc = () => qa('input[type=radio], input[type=checkbox]');
  const lbl = i => ((i.closest('label') || {}).innerText || '').trim().split('\n')[0];
  const tog = c => { let p = c; for (let k = 0; k < 5 && p; k++) p = p.parentElement; return ((p && p.innerText) || '').trim().split('\n')[0]; };
  const avail = () => rc().find(x => x.type === 'radio' && lbl(x) === AD.avail);
  const sv = () => qa('input[type=checkbox]').find(c => /^Самовывоз/.test(tog(c)));
  const deliv = () => qa('input[type=checkbox]').filter(c => c.checked && /^(Самовывоз|В пункт|Курьер)/.test(tog(c)));
  const press = async (get, want) => { for (const [m, f] of [['label.click', i => (i.closest('label') || i).click()], ['input.click', i => i.click()], ['fire(label)', i => fire(i.closest('label') || i)]]) {
      const cur = get(); if (!cur) return 'нет элемента'; if (cur.checked === want) return 'уже';
      f(cur); await sleep(700); const now = get(); if (now && now.checked === want) return m; }
    return 'НЕ ПОЛУЧИЛОСЬ'; };
  const good = () => { const a = avail(), s = sv(); return !!a && a.checked && (!s || !s.checked); };
  // после выбора адреса Авито пересчитывает блок доставки и сбрасывает «Под заказ» и самовывоз — жать, пока не устоится
  const t0 = Date.now(); let stable = 0;
  for (let k = 0; k < 7 && stable < 2; k++) { const a = await press(avail, true), d = await press(sv, false); if (a !== 'уже' || d !== 'уже') L('проход ' + (k + 1) + ': «' + AD.avail + '» — ' + a + '; самовывоз — ' + d); await sleep(1800); stable = good() ? stable + 1 : 0; }
  L('блок доставки устоялся за ' + Math.round((Date.now() - t0) / 1000) + ' с: ' + (stable >= 2));
  for (const c of qa('input[type=checkbox]')) if (c.checked && /^(Несколько штук в наличии|Можно оптом)/.test(tog(c))) (c.closest('label') || c).click();
  const cIn = () => qa('input').find(i => i.type === 'text' && /^(Россия|Казахстан)$/.test(i.value));
  const ci = cIn();
  if (ci && ci.value !== 'Казахстан') { ci.scrollIntoView({block: 'center'}); fire(ci); await sleep(300); setVal(ci, ''); await sleep(200); setVal(ci, 'Казах'); const o = await waitFor(() => [...document.querySelectorAll('body *')].find(e => e.children.length === 0 && e.textContent.trim() === 'Казахстан' && vis(e)), 3500); if (o) { o.scrollIntoView({block: 'center'}); fire(o); await sleep(900); } }
  for (let k = 0; k < 2 && (TA().value || '').length < AD.desc.length - 5; k++) { const ta = TA(); setVal(ta, AD.desc); ta.dispatchEvent(new FocusEvent('focusout', {bubbles: true})); ta.blur(); await sleep(1300); }
  if (hv('price') !== AD.price) { const a = qa('input'), h = q('input[name=price]'), el = h && a.slice(0, a.indexOf(h)).reverse().find(i => i.type === 'text' && i.offsetParent); if (el) { setVal(el, AD.price); el.blur(); } }
  await sleep(1200);
  const t = M().innerText, chk = rc().filter(i => i.checked).map(lbl);
  const S = {title: (document.querySelector('input[name=title]') || {}).value === AD.title, price: hv('price') === AD.price, img: !!hv('images[]'), addr: addrOk(), country: (cIn() || {}).value || 'нет', vid: qa('input').some(i => i.value === 'Товар приобретён на продажу'), desc: TA().value.length, chk: chk.join(','), deliv: deliv().length, tnved: /Сначала введите ТН ВЭД/.test(t), err: /Введите значение|Не удалось сохранить адрес/.test(t), mgr: hv('manager') || '', stable};
  L('ПРОВЕРКА ' + JSON.stringify(S));
  const ok = S.title && S.price && S.img && S.addr && S.country !== 'Россия' && S.vid && S.desc >= AD.desc.length - 5 && chk.includes('Новое') && chk.includes(AD.avail) && !S.deliv && !S.tnved && !S.err && !S.mgr && stable >= 2;
  if (ok) { const btn = qa('button').find(b => vis(b) && b.innerText.trim().startsWith('Продолжить')); btn.scrollIntoView({block: 'center'}); L('«Продолжить» нажмётся через полсекунды'); setTimeout(() => btn.click(), 600); } else L('НЕ жму «Продолжить»');
}
} catch (e) { L('ОШИБКА ' + String((e && e.stack) || e).slice(0, 300)); }
log
