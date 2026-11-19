/* Корзина «Наш декор» (с 19.11.2026).
   Покупатель складывает товары с разных страниц и оформляет их ОДНИМ заказом → CRM (/api/lead, intent "buy";
   CRM сама разбирает строки «Товар: A907 (…) — 8 шт» в позиции сделки).
   Корзина хранится в браузере покупателя (localStorage, ключ nd_cart). Нет хранилища — живёт до закрытия страницы.
   Старые формы «Купить» и «Заявка» на страницах товаров работают как раньше — корзина их не заменяет.
   Аварийно вернуть сайт без корзины: CRM → 🛟 (crm.nashdekor.ru/rescue/) → «Версии сайта» → прошлая версия. */
(() => {
"use strict";
if (window.NDCart) return;
const KEY = "nd_cart";
const ON_SITE = /(^|\.)nashdekor\.ru$/.test(location.hostname);
const LEAD_API = "https://crm.nashdekor.ru/api/lead";
const CAT_API = "https://crm.nashdekor.ru/api/catalog";
const HIT_API = "https://crm.nashdekor.ru/api/hit";
const fmt = n => Math.round(n).toLocaleString("ru-RU");
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- хранение ---------- */
let mem = [];
const clampQ = q => Math.max(1, Math.min(9999, parseInt(q, 10) || 1));
function clean(i){
  if (!i || typeof i.a !== "string" || !i.a.trim()) return null;
  return { a: i.a.trim().slice(0, 30), n: String(i.n || i.a).slice(0, 120), k: String(i.k || "").slice(0, 60),
           c: String(i.c || "").slice(0, 80), cl: i.cl === "декор" ? "декор" : "цвет", q: clampQ(i.q),
           r: Math.max(0, +i.r || 0), b: Math.max(0, parseInt(i.b, 10) || 0), u: String(i.u || "").slice(0, 200), img: String(i.img || "").slice(0, 300) };
}
function load(){
  try {
    const j = JSON.parse(localStorage.getItem(KEY) || "null");
    if (j && Array.isArray(j.items)) return j.items.map(clean).filter(Boolean);
  } catch (e) {}
  return mem.map(clean).filter(Boolean);
}
function save(items){
  shipStale("cart");
  mem = items;
  try { localStorage.setItem(KEY, JSON.stringify({ v: 1, t: Date.now(), items })); } catch (e) {}
  paint();
}
const keyOf = i => i.a + "|" + (i.c || "");

/* ---------- значок в шапке ---------- */
function cartUrl(){ const l = document.querySelector("a.cartlink"); return l ? l.href : "/korzina/"; }
function paint(){
  const n = load().length;
  document.querySelectorAll(".cartn").forEach(b => { b.textContent = n; b.hidden = n === 0; });
  document.querySelectorAll("a.cartlink").forEach(l => l.setAttribute("aria-label", n ? `Корзина: ${n} ${plural(n, "позиция", "позиции", "позиций")}` : "Корзина"));
}
function plural(n, one, few, many){ const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many; }

/* ---------- стили (свои классы ndk-*, цвета — из брендбука сайта) ---------- */
function css(){
  if ($("ndkCss")) return;
  const s = document.createElement("style"); s.id = "ndkCss";
  s.textContent =
    ".ndk-toast{position:fixed;left:50%;top:calc(env(safe-area-inset-top,0px) + 68px);transform:translateX(-50%);z-index:1002;width:min(440px,calc(100vw - 32px));"
    + "background:var(--paper,#fff);color:var(--ink,#26292E);border:1px solid var(--line,#D9DEE3);border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.18);padding:14px 16px;font-size:15px}"
    + ".ndk-toast b{display:block;margin-bottom:2px}.ndk-toast .ndk-row{display:flex;gap:8px;margin-top:12px}.ndk-toast .btn{flex:1;margin:0;padding:10px 8px;white-space:nowrap}"
    + ".ndk-toast .ndk-x{position:absolute;right:6px;top:4px;background:none;border:0;font-size:22px;line-height:1;color:var(--muted,#6b7280);padding:6px;cursor:pointer}"
    + ".ndk-list{display:grid;gap:12px;margin:8px 0 16px}"
    + ".ndk-item{display:grid;grid-template-columns:96px 1fr auto;gap:12px 16px;align-items:start;background:var(--paper,#fff);border:1px solid var(--line,#D9DEE3);border-radius:8px;padding:12px}"
    + ".ndk-item img{width:96px;height:56px;object-fit:cover;border-radius:4px;background:#26292E;display:block}"
    + ".ndk-item .ndk-n{font-weight:600;color:var(--ink,#26292E);text-decoration:none}.ndk-item .ndk-n:hover{text-decoration:underline}"
    + ".ndk-item .ndk-m{font-size:13px;color:var(--muted,#6b7280);margin-top:2px}.ndk-item .ndk-st{font-size:13px;margin-top:2px;color:var(--muted,#6b7280)}.ndk-item .ndk-st.ndk-ok{color:var(--good,#2e7d32)}"
    + ".ndk-q{display:flex;align-items:center;gap:6px;margin-top:10px;flex-wrap:wrap}"
    + ".ndk-q button{width:36px;height:36px;border:1px solid var(--line,#D9DEE3);background:var(--paper,#fff);color:var(--ink,#26292E);border-radius:6px;font-size:18px;cursor:pointer}"
    + ".ndk-q input{width:72px;height:36px;border:1px solid var(--line,#D9DEE3);border-radius:6px;text-align:center;font:inherit;font-size:16px;background:var(--paper,#fff);color:var(--ink,#26292E)}"
    + ".ndk-q small{color:var(--muted,#6b7280);font-size:13px}"
    + ".ndk-sum{text-align:right;white-space:nowrap}.ndk-sum b{display:block;font-size:17px}.ndk-sum small{color:var(--muted,#6b7280);font-size:13px}"
    + ".ndk-del{background:none;border:0;color:var(--muted,#6b7280);text-decoration:underline;font:inherit;font-size:13px;padding:8px 0 0;cursor:pointer}"
    + ".ndk-tot{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;border-top:1px solid var(--line,#D9DEE3);padding-top:14px;margin-bottom:6px}"
    + ".ndk-tot b{font-size:22px}.ndk-empty{padding:24px 0 8px;font-size:16px}"
    + ".cadd{margin-top:8px}.cadd .btn{width:100%;margin:0}"
    + ".ndk-step{display:flex;align-items:center;justify-content:space-between;background:var(--accent,#26292E);color:var(--accent-ink,#fff);border-radius:6px;height:36px;overflow:hidden}"
    + ".ndk-step button{width:44px;height:100%;background:none;border:0;color:inherit;font-size:20px;line-height:1;cursor:pointer;padding:0}"
    + ".ndk-step a{color:inherit;text-decoration:none;font-weight:600;font-size:14px;flex:1;text-align:center;line-height:36px}"
    + ".ndk-note{margin:10px 0 0;font-size:14px}.ndk-note a{color:var(--ink,#26292E)}"
    + ".ndk-fly{position:fixed;width:40px;height:40px;border-radius:50%;object-fit:cover;background:var(--accent,#26292E);z-index:1003;pointer-events:none;box-shadow:0 4px 14px rgba(0,0,0,.25)}"
    + ".ndk-ship{margin-top:14px;border-top:1px solid var(--line,#D9DEE3);padding-top:12px;font-size:14px}.ndk-ship>b{display:block;font-size:15px}"
    + ".ndk-shipf{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 6px;max-width:100%}.ndk-shipf input{flex:1 1 150px;width:auto;min-width:0;box-sizing:border-box;height:38px;border:1px solid var(--line,#D9DEE3);border-radius:6px;padding:0 10px;font:inherit;font-size:16px;background:var(--paper,#fff);color:var(--ink,#26292E)}"
    + ".ndk-shipf .btn{margin:0;white-space:nowrap;flex:0 0 auto;width:auto!important}.ndk-shipr small{display:block;color:var(--muted,#6b7280);margin-top:4px;font-size:12.5px}.ndk-shipr b{white-space:nowrap}.ndk-fill .btn{margin:6px 0 0;display:inline-block;width:auto!important}"
    + "@media (max-width:560px){.ndk-tot{flex-direction:column;align-items:flex-start;gap:2px}.ndk-item{grid-template-columns:72px 1fr}.ndk-item img{width:72px;height:42px}.ndk-sum{grid-column:2;text-align:left}}";
  document.head.appendChild(s);
}

/* ---------- «Добавлено в корзину» ---------- */
let toastT = 0;
function toast(it, total){
  css();
  let t = $("ndkToast");
  if (!t) { t = document.createElement("div"); t.id = "ndkToast"; t.className = "ndk-toast"; t.setAttribute("role", "status"); t.setAttribute("aria-live", "polite"); document.body.appendChild(t); }
  t.innerHTML = `<button type="button" class="ndk-x" aria-label="Закрыть">×</button><b>Добавлено в корзину</b>${esc(it.a)}${it.c ? " · " + esc(it.c) : ""} — ${fmt(total)} шт в корзине`
    + `<div class="ndk-row"><a class="btn" href="${esc(cartUrl())}">Оформить заказ</a><button type="button" class="btn ghost ndk-go">Продолжить</button></div>`;
  t.hidden = false;
  const close = () => { t.hidden = true; clearTimeout(toastT); };
  t.querySelector(".ndk-x").onclick = close; t.querySelector(".ndk-go").onclick = close;
  clearTimeout(toastT); toastT = setTimeout(close, 8000);
}

function add(it, from){
  const x = clean(it); if (!x) return 0;
  const items = load(), ex = items.find(i => keyOf(i) === keyOf(x));
  if (ex) { ex.q = Math.min(9999, ex.q + x.q); if (x.r) ex.r = x.r; if (x.img) ex.img = x.img; }
  else items.push(x);
  save(items);
  fly(from, x.img);
  toast(x, ex ? ex.q : x.q);
  syncAll();
  return items.length;
}
function setQty(key, q){
  const items = load(), i = items.findIndex(x => keyOf(x) === key);
  if (i < 0) return;
  if (q <= 0) items.splice(i, 1); else items[i].q = clampQ(q);
  save(items); syncAll();
}

/* «летит в корзину»: картинка товара (или кружок) от кнопки к значку корзины, значок «подпрыгивает» */
function pop(){
  if (reduce()) return;
  document.querySelectorAll(".cartn").forEach(b => { if (b.animate) b.animate([{ transform: "scale(1)" }, { transform: "scale(1.6)" }, { transform: "scale(1)" }], { duration: 380, easing: "ease-out" }); });
}
function fly(from, img){
  const to = [...document.querySelectorAll("a.cartlink")].find(l => l.getClientRects().length);
  if (!from || !to || reduce() || !document.body.animate) return pop();
  css();
  const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
  const d = document.createElement(img ? "img" : "div"); if (img) { d.src = img; d.alt = ""; }
  d.className = "ndk-fly"; d.setAttribute("aria-hidden", "true");
  const x0 = a.left + a.width / 2 - 20, y0 = a.top + a.height / 2 - 20, dx = b.left + b.width / 2 - 20 - x0, dy = b.top + b.height / 2 - 20 - y0;
  d.style.left = x0 + "px"; d.style.top = y0 + "px"; document.body.appendChild(d);
  const an = d.animate([{ transform: "translate(0,0) scale(1)", opacity: 1 },
                        { transform: `translate(${dx * 0.45}px,${dy * 0.45 - 70}px) scale(.85)`, opacity: 1, offset: 0.45 },
                        { transform: `translate(${dx}px,${dy}px) scale(.3)`, opacity: 0.5 }], { duration: 700, easing: "ease-in" });
  an.onfinish = an.oncancel = () => { d.remove(); pop(); };
}

/* ---------- карточки товаров: «В корзину» → [− N шт +] ----------
   Разметка: <div class="cadd" data-cart-add data-a data-k data-c data-cl data-r data-b data-u data-img> (страницы разделов),
   на главной data-home="1" — данные (и выбранный цвет) даёт window.NDCartItem(артикул). */
function infoOf(el){
  const d = el.dataset;
  if (d.home && typeof window.NDCartItem === "function") { try { return clean(Object.assign(window.NDCartItem(d.a) || {}, { q: 1 })); } catch (e) { return null; } }
  return clean({ a: d.a, k: d.k, c: d.c, cl: d.cl, r: +d.r || 0, b: +d.b || 0, u: d.u, img: d.img, q: 1 });
}
const qtyOf = key => { const i = load().find(x => keyOf(x) === key); return i ? i.q : 0; };
function syncCtl(el){
  const it = infoOf(el); if (!it) return;
  const q = qtyOf(keyOf(it)), st = q ? "s" + q : "a";
  if (el.dataset.st === st) return;
  el.dataset.st = st;
  el.innerHTML = q
    ? `<div class="ndk-step" role="group" aria-label="${esc(it.a)} в корзине"><button type="button" data-s="-1" aria-label="Убрать одну штуку">−</button><a href="${esc(cartUrl())}" title="Перейти в корзину">${fmt(q)} шт в корзине</a><button type="button" data-s="1" aria-label="Добавить ещё одну">+</button></div>`
    : '<button type="button" class="btn sm ndk-add">В корзину</button>';
}
function noteSync(el){
  const a = el.dataset.cartNote, q = load().filter(i => i.a === a).reduce((s, i) => s + i.q, 0);
  el.hidden = !q;
  if (q) el.innerHTML = `В корзине: <b>${fmt(q)} шт</b> · <a href="${esc(cartUrl())}">Оформить заказ</a>`;
}
let syncRaf = 0;
function syncAll(){
  cancelAnimationFrame(syncRaf);
  syncRaf = requestAnimationFrame(() => {
    const ctl = document.querySelectorAll("[data-cart-add]"); if (ctl.length) css();
    ctl.forEach(syncCtl); document.querySelectorAll("[data-cart-note]").forEach(noteSync);
  });
}
document.addEventListener("click", e => {
  const el = e.target.closest && e.target.closest("[data-cart-add]");
  if (!el) { syncAll(); return; }                 // на главной выбор цвета меняет, какая строка корзины у карточки
  const b = e.target.closest("button"); if (!b || !el.contains(b)) return;   // «N шт в корзине» — обычная ссылка в корзину
  e.preventDefault(); e.stopPropagation();
  const it = infoOf(el); if (!it) return;
  if (b.classList.contains("ndk-add")) add(it, b);
  else setQty(keyOf(it), qtyOf(keyOf(it)) + (+b.dataset.s || 0));
}, true);
if (window.MutationObserver) new MutationObserver(ms => { if (ms.some(m => [...m.addedNodes].some(n => n.nodeType === 1 && (n.matches("[data-cart-add]") || n.querySelector("[data-cart-add]"))))) syncAll(); })
  .observe(document.documentElement, { childList: true, subtree: true });

window.NDCart = { add, items: load, count: () => load().length, clear: () => { save([]); syncAll(); }, refresh: () => syncAll() };
addEventListener("storage", e => { if (e.key === KEY) { paint(); syncAll(); if (box) render(); } });
document.addEventListener("pageshow", paint);

/* ================= страница корзины /korzina/ ================= */
const box = $("ndCart");
let stock = {};                 // артикул → остаток на складе из CRM (если CRM ответила)
const stockText = q => q > 0 ? `В наличии: ${fmt(q)} шт` : "Под заказ, 3–4 недели";

function packText(i){
  if (!i.b) return "";
  const boxes = Math.floor(i.q / i.b), rest = i.q % i.b;
  return boxes ? `${boxes} кор.${rest ? " + " + rest + " шт" : ""} · в коробке ${i.b} шт` : `в коробке ${i.b} шт`;
}
function total(items){ return items.reduce((s, i) => s + i.q * i.r, 0); }
function render(){
  if (!box) return;
  css();
  const items = load(), form = $("cartOrder");
  document.querySelectorAll('[data-ship="cart"].ndk-ship').forEach(el => { el.hidden = !items.length; });
  if (!items.length) {
    if (!box.dataset.done) box.innerHTML = `<p class="ndk-empty">Корзина пуста. Выберите товары в <a href="${esc(box.dataset.catalog || "/catalog/stenovye-paneli/")}" style="color:var(--ink)">каталоге</a> — на странице товара кнопка «В корзину».</p>`;
    if (form) form.hidden = true;
    return;
  }
  box.dataset.done = "";
  const sum = total(items), noPrice = items.some(i => !i.r);
  box.innerHTML = '<div class="ndk-list">' + items.map((i, n) => {
    const q = stock[i.a];
    const st = q === undefined ? "" : `<div class="ndk-st${q > 0 ? " ndk-ok" : ""}">${esc(stockText(q))}</div>`;
    const img = i.img ? `<a href="${esc(i.u || "#")}" tabindex="-1" aria-hidden="true"><img src="${esc(i.img)}" alt="" width="96" height="56" loading="lazy"></a>` : '<span></span>';
    return `<div class="ndk-item" data-i="${n}">${img}<div><a class="ndk-n" href="${esc(i.u || "#")}">${esc(i.k ? i.k + " " + i.a : i.n)}</a>`
      + `<div class="ndk-m">${i.c ? (i.cl === "декор" ? "Декор: " : "Цвет: ") + esc(i.c) : ""}</div>${st}`
      + `<div class="ndk-q"><button type="button" data-d="-1" aria-label="Меньше">−</button><input type="number" min="1" max="9999" inputmode="numeric" value="${i.q}" aria-label="Количество ${esc(i.a)}, штук">`
      + `<span>шт</span><button type="button" data-d="1" aria-label="Больше">+</button>${i.b ? `<small>${esc(packText(i))}</small>` : ""}</div>`
      + `<button type="button" class="ndk-del">Убрать</button></div>`
      + `<div class="ndk-sum"><b class="num">${i.r ? fmt(i.q * i.r) + " ₽" : "По запросу"}</b><small>${i.r ? fmt(i.r) + " ₽ за шт" : ""}</small></div></div>`;
  }).join("") + "</div>"
    + `<div class="ndk-tot"><span>Итого, предварительно${noPrice ? " (без позиций «по запросу»)" : ""}</span><b class="num">${sum ? fmt(sum) + " ₽" : "По запросу"}</b></div>`
    + '<p class="fine" style="margin-top:0">Цены без НДС. Наличие, дату и стоимость доставки подтвердит менеджер — заказ ни к чему не обязывает до оплаты.</p>';
  if (form) form.hidden = false;
  const oSum = $("kSum"); if (oSum) oSum.textContent = sum ? "≈ " + fmt(sum) + " ₽" : "цена по запросу";
  const oN = $("kN"); if (oN) oN.textContent = items.length + " " + plural(items.length, "позиция", "позиции", "позиций");
  box.querySelectorAll(".ndk-item").forEach(row => {
    const n = +row.dataset.i;
    const setQ = q => { const all = load(); if (!all[n]) return; all[n].q = clampQ(q); save(all); render(); };
    row.querySelectorAll("[data-d]").forEach(b => b.onclick = () => { const all = load(); if (all[n]) setQ(all[n].q + +b.dataset.d); });
    const inp = row.querySelector("input");
    inp.onchange = () => setQ(inp.value);
    row.querySelector(".ndk-del").onclick = () => { const all = load(); all.splice(n, 1); save(all); render(); };
  });
}

/* текст заказа для CRM: одна строка на артикул (CRM разбирает «Товар: АРТИКУЛ (…) — N шт» в позиции сделки) */
function orderText(items){
  const by = new Map();
  items.forEach(i => { const g = by.get(i.a) || { a: i.a, k: i.k, cl: i.cl, q: 0, sum: 0, parts: [] }; g.q += i.q; g.sum += i.q * i.r; if (i.c) g.parts.push([i.c, i.q]); by.set(i.a, g); });
  const lines = [...by.values()].map(g => `Товар: ${g.a} (${(g.k || "товар").toLowerCase()}) — ${g.q} шт${g.parts.length ? ", " + g.cl + ": " + (g.parts.length === 1 ? g.parts[0][0] : g.parts.map(([c, q]) => c + " — " + q + " шт").join("; ")) : ""}${g.sum ? ", ≈ " + fmt(g.sum) + " ₽" : ""}`);
  const sum = total(items);
  return ("Заказ из корзины сайта, позиций: " + by.size + "\n" + lines.join("\n") + (sum ? `\nИтого ≈ ${fmt(sum)} ₽ (предварительно)` : "")).slice(0, 3900);
}

const WHO = { "Дизайнер": "designer", "Компания, объект": "company", "Ремонтная бригада": "company" };
async function sendLead(lead){
  if (!ON_SITE) return null;
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 12000);
  try {
    const r = await fetch(LEAD_API, { method: "POST", mode: "cors", credentials: "omit", signal: ctl.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: lead.name, contact: lead.contact, email: lead.email || "", who: WHO[lead.who] || "private",
        message: [lead.who && lead.who !== "Делаю ремонт у себя" ? "Кто: " + lead.who : "", lead.message].filter(Boolean).join("\n"),
        calc: lead.calc, total: lead.total, consent: true, consentAt: lead.consentAt, consentVersion: lead.consentVersion,
        intent: "buy", address: lead.address || "", website: ($("kHp") || {}).value || "",
        max: window.NDMax && NDMax.lead ? NDMax.lead() : undefined }) });
    const j = await r.json().catch(() => ({}));
    return r.ok && j.ok === true ? (j.id || true) : null;
  } catch (e) { return null; } finally { clearTimeout(timer); }
}
function hitOrder(){
  if (!ON_SITE || !navigator.sendBeacon || navigator.doNotTrack === "1" || navigator.globalPrivacyControl) return;
  try { navigator.sendBeacon(HIT_API, new Blob([JSON.stringify({ e: [["lead", "cart", "buy"]], r: "", u: "", m: matchMedia("(pointer: coarse)").matches ? 1 : 0 })], { type: "text/plain" })); } catch (e) {}
}
function msgLinks(){
  const mx = box.dataset.max, tg = box.dataset.tg;
  return [mx && `<a href="${esc(mx)}?start=site" target="_blank" rel="noopener" data-max>MAX</a>`, tg && `<a href="${esc(tg)}?start=site" target="_blank" rel="noopener" data-tg>Telegram</a>`].filter(Boolean).join(" или ") || "чат на сайте";
}

function initForm(){
  const f = $("kForm"); if (!f) return;
  const shipUI = () => { const d = f.querySelector('input[name="kship"]:checked'); const pick = d && d.value === "pickup"; $("kAddr").hidden = pick; $("kAddr").required = !pick; };
  f.querySelectorAll('input[name="kship"]').forEach(r => r.addEventListener("change", shipUI)); shipUI();
  f.addEventListener("submit", async e => {
    e.preventDefault();
    const items = load(), err = $("kErr");
    const fail = (t, el) => { err.textContent = t; err.hidden = false; if (el) el.focus(); };
    if (!items.length) return fail("Корзина пуста — добавьте товары на странице товара.");
    const name = $("kName").value.trim(), contact = $("kContact").value.trim();
    if (!name || !contact) return fail("Укажите имя и телефон или ник в мессенджере — по ним мы ответим.", !name ? $("kName") : $("kContact"));
    const pickup = (f.querySelector('input[name="kship"]:checked') || {}).value === "pickup";
    const addr = pickup ? "Самовывоз, СПб" : $("kAddr").value.trim();
    if (!addr) return fail("Укажите адрес доставки или выберите самовывоз.", $("kAddr"));
    if (!$("kAgree").checked) return fail("Отметьте согласие на обработку данных и условия продажи.", $("kAgree"));
    err.hidden = true;
    const lead = { name, contact, email: $("kEmail").value.trim(), who: $("kWho").value, message: [$("kMsg").value.trim(), window.NDShip.text()].filter(Boolean).join("\n"),
                   calc: orderText(items), total: Math.round(total(items)), consentAt: new Date().toISOString(), consentVersion: "2026-10-29", address: addr };
    const btn = $("kSend"); btn.disabled = true; btn.textContent = "Отправляем…";
    const id = await sendLead(lead);
    btn.disabled = false; btn.textContent = "Оформить заказ";
    const done = $("kDone"); done.hidden = false;
    if (id) {
      hitOrder();
      const no = typeof id === "number" || /^\d+$/.test(String(id)) ? ` №${id}` : "";
      done.innerHTML = `<div class="stack" style="gap:12px"><div class="ok" role="status"><b id="kThanks"></b>Менеджер проверит наличие, уточнит дату и время доставки и пришлёт ссылку на оплату картой или через СБП${lead.email ? " (копию — на " + esc(lead.email) + ")" : ""} в рабочее время. Оплата до отгрузки, чек придёт на e-mail; компаниям и ИП — счёт.`
        + `<p>Свяжемся с вами:<br><span id="kTo" style="white-space:nowrap;font-weight:600"></span></p><p>Если в номере ошибка — напишите нам в ${msgLinks()}.</p>`
        + `<p style="font-size:14px">Вернуть неподошедший товар можно в течение 7 дней после получения, если он не распилен, не окрашен и не монтировался; товар с браком — по закону. <a href="${esc(cartUrl().replace(/korzina\/?$/, "oplata/#vozvrat"))}" style="color:inherit">Условия возврата</a></p></div></div>`;   // условия возврата — только после заказа (19.11.2026)
      $("kThanks").textContent = `Спасибо, ${name}! Заказ${no} принят. `; $("kTo").textContent = contact;
      f.reset(); f.hidden = true; box.dataset.done = "1"; save([]);
      box.innerHTML = '<p class="ndk-empty">Заказ отправлен, корзина очищена.</p>';
      const sec = $("cartOrder"); if (sec) sec.hidden = false;
      done.scrollIntoView({ block: "center", behavior: reduce() ? "auto" : "smooth" });
    } else {
      const text = `Заказ: ${name}, ${contact}${lead.email ? ", " + lead.email : ""} (${lead.who})\nПолучение: ${addr}${lead.message ? "\n" + lead.message : ""}\n${lead.calc}`;
      done.innerHTML = `<div class="stack" style="gap:8px"><div class="err">Заказ сейчас не отправляется. Скопируйте текст и пришлите его в ${msgLinks()} — корзина сохранена.</div><pre class="copy" id="kText"></pre><button class="btn sm" type="button" id="kCopy">Копировать заказ</button></div>`;
      $("kText").textContent = text;
      $("kCopy").onclick = async ev => { const b = ev.currentTarget; try { await navigator.clipboard.writeText(text); b.textContent = "Скопировано"; } catch (x) { b.textContent = "Выделите и скопируйте"; } setTimeout(() => b.textContent = "Копировать заказ", 1800); };
    }
  });
}

async function prices(){
  if (!ON_SITE) return;
  try {
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 5000);
    const r = await fetch(CAT_API, { signal: ctl.signal, credentials: "omit" }); clearTimeout(t);
    if (!r.ok) return;
    const cat = (await r.json()).items || {};
    const items = load(); let ch = false;
    items.forEach(i => { const k = cat[i.a]; if (!k) return; stock[i.a] = Math.max(0, k.q | 0); if (k.p > 0 && k.p !== i.r) { i.r = k.p; ch = true; } });
    if (ch) save(items);
    render();
  } catch (e) {}
}

/* ---------- доставка ПЭК в другой город (с 19.11.2026) ----------
   Блок <div data-ship="item" data-a="A907"> на странице товара и <div data-ship="cart"> в корзине. Показывается, только если
   в CRM включён расчёт (Настройки → «ПЭК — расчёт доставки»); CRM спрашивает ПЭК: до терминала, а с улицей — и до двери.
   СПб и Ленобласть (с 19.11): только до двери по адресу с улицей — ориентир; везём ПЭК или другим вариантом, что выгоднее. */
const SHIP_API = "https://crm.nashdekor.ru/api/ship";
const CITY_KEY = "nd_city";
const CITIES = ["Москва", "Казань", "Нижний Новгород", "Екатеринбург", "Новосибирск", "Краснодар", "Ростов-на-Дону", "Самара",
  "Воронеж", "Пермь", "Уфа", "Челябинск", "Волгоград", "Тверь", "Великий Новгород", "Псков", "Петрозаводск", "Мурманск",
  "Архангельск", "Вологда", "Череповец", "Ярославль", "Калининград", "Сочи", "Новороссийск", "Тула", "Рязань", "Владимир",
  "Иваново", "Кострома", "Калуга", "Смоленск", "Брянск", "Белгород", "Курск", "Липецк", "Тамбов", "Орёл", "Пенза", "Саратов",
  "Ульяновск", "Тольятти", "Оренбург", "Тюмень", "Омск", "Томск", "Красноярск", "Барнаул", "Иркутск", "Хабаровск",
  "Владивосток", "Ставрополь", "Махачкала", "Чебоксары", "Ижевск", "Киров", "Сыктывкар", "Набережные Челны", "Сургут",
  "Симферополь", "Севастополь", "Кемерово", "Новокузнецк", "Астрахань", "Магнитогорск"];
let shipLast = null;           // последний расчёт: {mode, a, city, text}
const getCity = () => { try { return localStorage.getItem(CITY_KEY) || ""; } catch (e) { return ""; } };
const setCity = v => { try { localStorage.setItem(CITY_KEY, v); } catch (e) {} };
function shipStale(mode){
  if (!shipLast || (mode && shipLast.mode !== mode)) return;
  shipLast = null;
  document.querySelectorAll(`[data-ship="${mode || "cart"}"] .ndk-shipr`).forEach(r => { if (r.innerHTML) r.innerHTML = "<small>Состав изменился — нажмите «Рассчитать» ещё раз.</small>"; });
}
/* введён адрес, а не только город (как has_street в CRM) */
const has_street = s => /(^|[\s,])(ул|улица|пр|просп|проспект|пер|переулок|ш|шоссе|наб|бульвар|б-р|пл|площадь|мкр|дом|д)\.?\s/i.test(s || "") || /,\s*\d+/.test(s || "");
function shipItems(el){
  if (el.dataset.ship === "cart") return load().map(i => ({ a: i.a, q: i.q }));
  const q = Math.max(1, parseInt(($("qty") || {}).value, 10) || 1);
  return [{ a: el.dataset.a, q }];
}
async function shipCalc(el, where){
  const res = el.querySelector(".ndk-shipr"), btn = el.querySelector("button");
  const items = shipItems(el);
  if (!items.length) { res.innerHTML = "<small>Сначала положите товары в корзину.</small>"; return; }
  btn.disabled = true; res.innerHTML = "<small>Считаем по тарифам ПЭК…</small>";
  let j = null, code = 0;
  try {
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 20000);
    const r = await fetch(SHIP_API, { method: "POST", mode: "cors", credentials: "omit", signal: ctl.signal,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ city: where, items }) });
    clearTimeout(t); code = r.status; j = await r.json().catch(() => null);
  } catch (e) { j = null; }
  btn.disabled = false;
  const note = "<small>В цене — забор груза с нашего склада. Ориентир по тарифам ПЭК на сегодня; точную сумму назовём при подтверждении заказа. Доставку оплачиваете в ПЭК при получении.</small>";
  if (j && j.ok && j.local) {                 /* СПб и Ленобласть: ПЭК до двери — ориентир; везём ПЭК или другим вариантом — что выгоднее */
    const d = j.door, alt = "Если другой вариант — например, грузовое такси — выйдет выгоднее или удобнее, предложим его при подтверждении заказа. Доставка по СПб и Ленобласти оплачивается вместе с товаром; самовывоз со склада — бесплатно.";
    if (d) {
      res.innerHTML = `По Петербургу и области ПЭК заберёт у нас и привезёт до двери: <b>≈ ${fmt(d.cost)} ₽</b><small>${alt}</small>`;
      shipLast = { mode: el.dataset.ship, a: el.dataset.a || "", city: where,
                   text: `Доставка по СПб/ЛО: ${where} — ПЭК до двери ≈ ${fmt(d.cost)} ₽ (расчёт на сайте; можно другим вариантом, если выгоднее)` };
      const addr = $("kAddr");
      if (el.dataset.ship === "cart" && addr && !addr.value.trim()) addr.value = where;
      return;
    }
    res.innerHTML = has_street(where)
      ? "По Петербургу и области доставим ПЭК или грузовым такси — что выгоднее и удобнее вам; стоимость назовём при подтверждении заказа. Самовывоз со склада — бесплатно."
      : `По Петербургу и области доставим ПЭК или другим вариантом — что выгоднее и удобнее вам; самовывоз со склада — бесплатно.<small>Введите адрес с улицей и домом — посчитаем доставку ПЭК до двери.</small>`;
    shipLast = null; return;
  }
  if (j && j.ok && j.terminal) {
    const t = j.terminal, d = j.door, days = x => x && x.days ? `, ≈ ${x.days} дн.` : "";
    /* неполная коробка в другой город — в жёсткой упаковке ПЭК (решение 19.11), подсказка «добрать до коробки» */
    const fill = Array.isArray(j.fill) ? j.fill.filter(f => f && f.add > 0) : [];
    let pack = j.packed ? "<small>Неполная коробка поедет в жёсткой упаковке ПЭК (обрешётка) — так тонкие рейки не ломаются в дороге; упаковка уже в цене.</small>"
      : j.pack_later ? "<small>Неполную коробку отправим в жёсткой упаковке ПЭК (обрешётка) — её стоимость назовём при подтверждении заказа.</small>" : "";
    if (fill.length) pack += `<small class="ndk-fill">${el.dataset.ship === "item" ? `До целой коробки ещё ${fill[0].add} шт`
      : "До целых коробок: " + fill.map(f => `${esc(f.a)} — ещё ${f.add} шт`).join(", ")}. Целой коробкой надёжнее и без доплаты за упаковку. `
      + `<button type="button" class="btn sm ghost ndk-fillb">Добрать до коробки</button></small>`;
    res.innerHTML = `До терминала ПЭК (${esc(j.branch)}): <b>≈ ${fmt(t.cost)} ₽</b>${days(t)}`
      + (d ? `<br>До двери: <b>≈ ${fmt(d.cost)} ₽</b>${days(d)}` : "<small>Введите адрес с улицей и домом — посчитаем и до двери.</small>") + pack + note;
    const fb = res.querySelector(".ndk-fillb");
    if (fb) fb.addEventListener("click", () => {
      if (el.dataset.ship === "item") { const qb = $("qBox"); if (qb) qb.click(); }
      else {
        const items = load();
        fill.forEach(f => { const same = items.filter(i => i.a === f.a); if (same.length === 1) setQty(keyOf(same[0]), same[0].q + f.add); });
        if (box) render();
      }
      shipCalc(el, where);
    });
    shipLast = { mode: el.dataset.ship, a: el.dataset.a || "", city: where,
                 text: `Доставка ПЭК: ${where} — до терминала ≈ ${fmt(t.cost)} ₽${t.days ? ", ≈ " + t.days + " дн." : ""}${d ? `, до двери ≈ ${fmt(d.cost)} ₽` : ""}${j.packed ? ", неполная коробка — в жёсткой упаковке ПЭК" : j.pack_later ? ", неполная коробка — в жёсткой упаковке ПЭК (упаковка не в расчёте)" : ""} (расчёт на сайте)` };
    const addr = $("kAddr");                                      // корзина: адрес с улицей — сразу в форму заказа
    if (el.dataset.ship === "cart" && d && addr && !addr.value.trim()) addr.value = where;
    return;
  }
  shipLast = null;
  const err = j && j.error;
  res.innerHTML = err === "city" ? "<small>ПЭК не нашёл такой город — проверьте название или добавьте область.</small>"
    : code === 429 ? "<small>Слишком много расчётов подряд — попробуйте через несколько минут.</small>"
    : "<small>Сейчас не получилось посчитать — стоимость доставки назовём при подтверждении заказа.</small>";
}
function renderShip(el){
  css();
  if (!$("ndkCities")) { const dl = document.createElement("datalist"); dl.id = "ndkCities"; dl.innerHTML = CITIES.map(c => `<option value="${esc(c)}">`).join(""); document.body.appendChild(dl); }
  el.classList.add("ndk-ship");
  el.innerHTML = '<b>Доставка ПЭК — посчитать стоимость</b><form class="ndk-shipf" novalidate><input type="text" list="ndkCities" autocomplete="address-level2" placeholder="Город или адрес" aria-label="Город или адрес доставки">'
    + '<button class="btn sm ghost" type="submit">Рассчитать</button></form><div class="ndk-shipr" aria-live="polite"></div>';
  const inp = el.querySelector("input"); inp.value = getCity();
  el.querySelector("form").addEventListener("submit", e => {
    e.preventDefault();
    const v = inp.value.replace(/\s+/g, " ").trim();
    if (v.length < 2) { inp.focus(); return; }
    setCity(v); shipCalc(el, v);
  });
  el.hidden = el.dataset.ship === "cart" && !load().length;
}
async function initShip(){
  const els = document.querySelectorAll("[data-ship]");
  if (!els.length || !ON_SITE) return;
  let on = false;
  try { const r = await fetch(SHIP_API, { credentials: "omit" }); on = !!((await r.json()) || {}).on; } catch (e) { on = false; }
  if (!on) return;                                    // расчёт выключен в CRM — блока нет, как раньше
  els.forEach(renderShip);
  ["qMinus", "qPlus", "qBox"].forEach(id => { const b = $(id); if (b) b.addEventListener("click", () => shipStale("item")); });
  if ($("qty")) $("qty").addEventListener("input", () => shipStale("item"));
}
window.NDShip = { text: a => shipLast && (!a || shipLast.a === a || shipLast.mode === "cart") ? shipLast.text : "" };

function start(){
  paint(); syncAll();
  if (box) { render(); initForm(); prices(); }
  initShip();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
