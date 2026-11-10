(() => {
const AD = {
  title: "Реечная панель под дерево 3-7 дуб, 3 ламели",
  price: "1045",
  desc: "Под заказ, срок поставки — 3–4 недели.\n\nТекст описания…",
  img: "https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/mebel/0f7s1eez/img/3-7.jpg",
  cat: "Стеновые панели, рейки и элементы декора",
  dims: {"Длина": 3000, "Ширина": 120},
  material: "Полистирол",
  avail: "Под заказ"
};
sessionStorage.setItem('nd_ad', JSON.stringify(AD));
const log = []; const L = x => { log.push(x); sessionStorage.setItem('nd_log', JSON.stringify(log)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
const fire = el => { const r = el.getBoundingClientRect(); const o = {bubbles: true, cancelable: true, view: window, clientX: r.x + Math.min(r.width / 2, 40), clientY: r.y + r.height / 2, button: 0, pointerId: 1, pointerType: 'mouse', isPrimary: true};
  for (const t of ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o)); };
const click = el => { el.scrollIntoView({block: 'center'}); fire(el); };
const leaves = () => [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && e.textContent.trim() && vis(e));
const waitFor = async (fn, ms = 6000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = fn(); if (v) return v; await sleep(250); } return null; };
const setVal = (el, v) => { const p = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; el.focus(); Object.getOwnPropertyDescriptor(p, 'value').set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); };
const guard = () => document.querySelectorAll('form').forEach(f => { if (!f.__nd) { f.__nd = 1; f.addEventListener('submit', e => e.preventDefault(), {capture: true}); } });
const M = () => document.querySelector('main') || document.body;
const q = s => M().querySelector(s), qa = s => [...M().querySelectorAll(s)];
const hv = n => (q('input[name="' + n + '"]') || {}).value;
const TA = () => q('textarea[name=description]'), AI = () => q('input[name="params[2855]"]');
(async () => { try {
  if (location.pathname !== '/additem') return L('не та страница ' + location.pathname);
  if (TA()) return L('форма уже открыта — нужна чистая страница /additem');
  guard();
  let title = document.querySelector('input[name=title]');
  if (!title) { const root = await waitFor(() => [...document.querySelectorAll('button')].find(e => vis(e) && e.innerText.trim() === 'Для дома и дачи'), 5000); if (root) root.click(); title = await waitFor(() => document.querySelector('input[name=title]'), 6000); }
  if (!title) return L('нет поля названия');
  setVal(title, AD.title); await sleep(200); title.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true, key: 'a'}));
  const chips = () => leaves().filter(e => /[·•]/.test(e.textContent));
  const chip = await waitFor(() => chips().find(e => e.textContent.includes(AD.cat)), 8000);
  if (!chip) return L('нет подсказки категории; предложено: ' + chips().map(e => e.textContent.trim().slice(0, 80)).join(' || '));
  click(chip);
  if (!await waitFor(TA, 10000)) return L('форма не открылась');
  await sleep(1500); guard();
  const crumbs = (M().innerText.match(/Товары[^\n]{10,}/) || [''])[0];
  if (!AD.cat.split(/[ ,]+/).some(w => w.length > 5 && crumbs.toLowerCase().includes(w.toLowerCase().slice(0, 6)))) return L('не та категория: ' + crumbs.slice(0, 160));
  L('категория: …' + crumbs.slice(-60));
  // выпадающие списки
  const lab = e => { let p = e; for (let k = 0; k < 7 && p; k++) { p = p.parentElement; const t = ((p && p.innerText) || '').trim().split('\n')[0].trim(); if (t && t.length < 60) return {t, p}; } return {t: '', p: e}; };
  const rules = [[/^Вид объявления/, 'Товар приобретён на продажу']]; if (AD.material) rules.push([/Материал/i, AD.material]);
  const seen = new Set();
  for (let n = 0; n < 10; n++) {
    const c = qa('[role=combobox]').find(x => !seen.has(lab(x).t)); if (!c) break;
    const {t: label, p: cont} = lab(c); seen.add(label);
    const rule = rules.find(r => r[0].test(label));
    if (!rule) { if (!/^%$|НДС|iPhone|Android|Где принимать/i.test(label)) L('список без правила: «' + label + '»'); continue; }
    const cur = [...cont.querySelectorAll('input')].map(i => i.value).concat(cont.innerText.split('\n').slice(1)).map(s => s.trim());
    if (cur.includes(rule[1])) continue;
    click(c); await sleep(1000);
    const find = () => [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && e.textContent.trim() === rule[1] && !c.contains(e));
    let o = find().find(vis);
    if (!o) { find().forEach(h => h.scrollIntoView({block: 'center'})); await sleep(500); o = find().find(vis); }
    if (!o) { L('«' + label + '»: нет варианта «' + rule[1] + '»'); document.body.click(); await sleep(400); continue; }
    click(o); await sleep(1000); L('«' + label + '» → ' + rule[1]);
  }
  // переключатели
  const rc = () => qa('input[type=radio], input[type=checkbox]');
  const lbl = i => ((i.closest('label') || {}).innerText || '').trim().split('\n')[0];
  const tick = t => { const i = rc().find(x => lbl(x) === t); if (i && !i.checked) (i.closest('label') || i).click(); };
  for (const t of ['Новое', AD.avail, 'Поштучно', 'Стены']) tick(t);
  if (/Подходит для улицы/.test(M().innerText)) tick('Нет');
  await sleep(1000); tick('Штуку'); await sleep(600);
  // размеры, минимальный заказ, цена
  const hctx = h => { let p = h; for (let k = 0; k < 6 && p; k++) { p = p.parentElement; const t = ((p && p.innerText) || '').trim(); if (t.length > 1 && t.length < 120) return t; } return ''; };
  for (const {n, c} of qa('input[type=hidden]').map(h => ({n: h.name, c: hctx(h)})).filter(x => x.n)) {
    const name = c.split('\n')[0].trim(), mm = AD.dims[name];
    const val = name === 'Минимальный заказ' ? '1' : !mm ? null : /см\s*$/.test(c) ? String(mm / 10).replace('.', ',') : /(^|\s)м\s*$/.test(c) ? String(mm / 1000).replace('.', ',') : String(mm);
    if (val === null || hv(n)) continue;
    const a = qa('input'), h = q('input[name="' + n + '"]'), el = a.slice(a.indexOf(h) + 1).find(i => i.type === 'text' && i.offsetParent);
    if (el) { setVal(el, val); el.blur(); await sleep(300); } L(name + '=' + hv(n));
  }
  { const a = qa('input'), h = q('input[name=price]'), el = h && a.slice(0, a.indexOf(h)).reverse().find(i => i.type === 'text' && i.offsetParent); if (el) { setVal(el, AD.price); el.blur(); await sleep(400); } }
  // фото
  const blob = await (await fetch(AD.img)).blob(); const fi = q('input[type=file]'); const dt = new DataTransfer(); dt.items.add(new File([blob], AD.img.split('/').pop(), {type: 'image/jpeg'})); fi.files = dt.files; fi.dispatchEvent(new Event('change', {bubbles: true}));
  await waitFor(() => hv('images[]'), 12000);
  // страна
  const cIn = () => qa('input').find(i => i.type === 'text' && /^(Россия|Казахстан)$/.test(i.value));
  const ci = await waitFor(cIn, 3000);
  if (ci && ci.value !== 'Казахстан') { click(ci); await sleep(300); setVal(ci, ''); await sleep(200); setVal(ci, 'Казах'); const o = await waitFor(() => leaves().find(e => e.textContent.trim() === 'Казахстан'), 4000); if (o) { click(o); await sleep(1000); } }
  // описание — всегда в свежий элемент
  for (let k = 0; k < 3 && (TA().value || '').length < AD.desc.length - 5; k++) { const ta = TA(); setVal(ta, AD.desc); ta.dispatchEvent(new FocusEvent('focusout', {bubbles: true})); ta.blur(); await sleep(1500); }
  L('цена=' + hv('price') + ' фото=' + (hv('images[]') || 'НЕТ') + ' страна=' + ((cIn() || {}).value || 'поля нет') + ' описание=' + TA().value.length + ' отмечено: ' + rc().filter(i => i.checked).map(lbl).join(','));
  AI().scrollIntoView({block: 'center'});
  L('ГОТОВО К АДРЕСУ');
} catch (e) { L('ОШИБКА ' + String((e && e.stack) || e).slice(0, 300)); } })();
return 'запущено';
})()
