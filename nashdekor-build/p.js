/* Страница товара и страницы разделов «Наш декор».
   Данные страницы — в window.P (собирает nashdekor-build/build.py). */
(() => {
"use strict";
const P = window.P || {};
const $ = id => document.getElementById(id);
const fmt = n => Math.round(n).toLocaleString("ru-RU");
const ROOT = P.root || "../../";
const ON_SITE = /(^|\.)nashdekor\.ru$/.test(location.hostname);
const WHITE = "#F6F4EF";

/* ---------- счётчик посещений (как на главной: без cookie, только «что открыли и что нажали») ---------- */
const HIT_API = "https://crm.nashdekor.ru/api/hit";
const hitOn = ON_SITE && !!navigator.sendBeacon && navigator.doNotTrack !== "1" && !navigator.globalPrivacyControl;
const hitQ = [], hitSeen = new Set(); let hitT = 0;
function hitSend(){
  clearTimeout(hitT);
  if (!hitOn || !hitQ.length) return;
  let r = ""; try { r = document.referrer ? new URL(document.referrer).hostname : ""; } catch (e) {}
  const body = { e: hitQ.splice(0, 40), r, u: (new URLSearchParams(location.search).get("utm_source") || "").slice(0, 30),
    m: matchMedia("(pointer: coarse)").matches ? 1 : 0 };
  try { navigator.sendBeacon(HIT_API, new Blob([JSON.stringify(body)], { type: "text/plain" })); } catch (e) {}
  if (hitQ.length) hitSend();
}
function hit(kind, key = "", act = ""){
  const id = kind + "|" + key + "|" + act;
  if (!hitOn || hitSeen.has(id)) return;
  hitSeen.add(id); hitQ.push([kind, String(key).slice(0, 40), act]);
  clearTimeout(hitT); hitT = setTimeout(hitSend, 4000);
}
if (hitOn) {
  hit("view", location.pathname); hitSend();
  addEventListener("pagehide", hitSend);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") hitSend(); });
}

/* ---------- цены и наличие из CRM (crm.nashdekor.ru → «Склад и цены») ---------- */
const CAT_API = "https://crm.nashdekor.ru/api/catalog";
async function loadCatalog(){
  if (!ON_SITE) return null;
  try {
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 5000);
    const r = await fetch(CAT_API, { signal: ctl.signal, credentials: "omit" });
    clearTimeout(t);
    if (!r.ok) return null;
    return (await r.json()).items || null;
  } catch (e) { return null; }
}
const stockText = q => q > 0 ? `В наличии: ${fmt(q)} шт` : "Под заказ, 3–4 недели";

/* ================= режим списка (страница раздела) ================= */
if (P.list) {
  loadCatalog().then(items => {
    if (!items) return;
    document.querySelectorAll("[data-p]").forEach(el => {
      const k = items[el.dataset.p]; if (!k) return;
      const pr = el.querySelector(".price b"), st = el.querySelector(".stock");
      if (pr && k.p > 0) pr.textContent = fmt(k.p) + " ₽";
      if (st) { const q = Math.max(0, k.q | 0); st.textContent = stockText(q); st.classList.toggle("ok", q > 0); }
    });
  });
  return;
}

/* ================= страница товара ================= */
const X = P.item; if (!X) return;
const PAINT = P.paint || [];
const isWood = X.c === "color";
let cur = { name: "Белый", hex: WHITE, code: "" };    // выбранный цвет покраски
let qty = 1;

/* ---------- цвет ---------- */
function renderDots(){
  const box = $("colors"); if (!box || isWood) return;
  const custom = !PAINT.some(([n]) => n === cur.name);
  box.innerHTML = `<div class="eyebrow">Цвет покраски</div>
    <div class="dots" role="group" aria-label="Цвет покраски">${PAINT.map(([n,h]) => `<button type="button" class="dot" data-name="${n}" data-hex="${h}" aria-pressed="${cur.name === n}" title="${n}" style="background:${h}"></button>`).join("")}
    <label class="dot own" title="Свой цвет" aria-pressed="${custom}" style="${custom ? `background:${cur.hex}` : ""}"><input type="color" id="ownColor" value="${custom ? cur.hex : "#9A8C7A"}" aria-label="Свой цвет"></label></div>
    <div class="cname">Цвет: <b id="cname"></b> <span class="note" id="cnote"></span></div>
    ${custom ? `<input type="text" class="ralcode" id="ral" value="${cur.code || ""}" placeholder="Код цвета (RAL, NCS), если есть" aria-label="Код своего цвета">` : ""}`;
  box.querySelectorAll("button.dot").forEach(b => b.addEventListener("click", () => {
    cur = { name: b.dataset.name, hex: b.dataset.hex, code: "" }; renderDots(); applyColor(); hit("item", X.a, "paint");
  }));
  const own = $("ownColor");
  own.addEventListener("input", () => { cur = { name: "Свой цвет", hex: own.value, code: cur.code || "" }; own.parentElement.style.background = own.value; own.parentElement.setAttribute("aria-pressed", "true"); box.querySelectorAll("button.dot").forEach(d => d.setAttribute("aria-pressed", "false")); applyColor(); });
  own.addEventListener("change", () => { renderDots(); applyColor(); hit("item", X.a, "paint"); });
  const ral = $("ral"); if (ral) ral.addEventListener("input", () => { cur.code = ral.value.trim(); applyColor(); });
  applyColorLabel();
}
const colorText = () => isWood ? X.d.split(",")[0] : cur.name + (cur.code ? " · " + cur.code : "") + (cur.name === "Свой цвет" ? " " + cur.hex : "");
function applyColorLabel(){
  if ($("cname")) $("cname").textContent = cur.name + (cur.code ? " · " + cur.code : "");
  if ($("cnote")) $("cnote").textContent = cur.name === "Белый" ? "— как с завода, под покраску" : cur.name === "Свой цвет" ? cur.hex : "";
}
function applyColor(){
  applyColorLabel();
  if (W3.setColor) W3.setColor(cur.hex);
  if (view === "photo") paintPhoto();
  updateLinks();
}
function updateLinks(){
  const a = $("toCalc"); if (!a) return;
  const q = new URLSearchParams({ panel: X.a });
  if (wall.used && wall.W && wall.H) { q.set("w", wall.W); q.set("h", wall.H); if (wall.open) q.set("o", wall.open); }
  if (!isWood && cur.name !== "Белый") { q.set("hex", cur.hex.slice(1)); q.set("cname", cur.name); if (cur.code) q.set("code", cur.code); }
  a.href = `${ROOT}?${q.toString()}#calc`;
  if ($("wFull")) $("wFull").href = a.href;
}

/* ---------- перекраска фото: красим светлые малонасыщенные пиксели (само изделие), синий фон не трогаем ---------- */
const PX = new Map(); let MIMG = null, maskLoading = false;
function prep(img){
  if (PX.has(img.src)) return PX.get(img.src);
  const w = img.naturalWidth, h = img.naturalHeight, c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, w, h).data, n = w * h, m = new Float32Array(n), L = new Float32Array(n), hist = new Uint32Array(256);
  const ss = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
  for (let i = 0, p = 0; i < n; i++, p += 4) {
    const r = d[p], gg = d[p+1], b = d[p+2], mx = Math.max(r, gg, b), mn = Math.min(r, gg, b);
    const s = mx ? (mx - mn) / mx : 0, v = mx / 255;
    const wgt = (1 - ss(0.16, 0.30, s)) * ss(0.22, 0.34, v) * (1 - ss(6, 16, r - b));
    m[i] = wgt; L[i] = 0.299 * r + 0.587 * gg + 0.114 * b;
    if (wgt > 0.6) hist[L[i] | 0]++;
  }
  if (MIMG) { const mc = document.createElement("canvas"); mc.width = w; mc.height = h; const mg = mc.getContext("2d"); mg.drawImage(MIMG, 0, 0, w, h);
    const md = mg.getImageData(0, 0, w, h).data; for (let i = 0; i < n; i++) m[i] *= md[i * 4] / 255; }
  let tot = 0; for (const k of hist) tot += k; let acc = 0, ref = 230;
  for (let k = 0; k < 256; k++) { acc += hist[k]; if (acc >= tot * 0.9) { ref = Math.max(120, k); break; } }
  const res = { w, h, d: new Uint8ClampedArray(d), m, L, ref };
  PX.set(img.src, res); return res;
}
function paintPhoto(){
  const img = $("photo"); if (!img || isWood) return;
  let cv = img.parentElement.querySelector("canvas.pc");
  if (cur.name === "Белый") { if (cv) cv.hidden = true; return; }
  if (!img.complete || !img.naturalWidth) { img.addEventListener("load", paintPhoto, { once: true }); return; }
  if (P.mask && !MIMG) { if (!maskLoading) { maskLoading = true; const mi = new Image(); mi.onload = () => { MIMG = mi; PX.clear(); paintPhoto(); }; mi.onerror = () => { P.mask = false; paintPhoto(); }; mi.src = ROOT + "img/mask/" + P.photo.split("/").pop().split("?")[0].replace(".jpg", ".png"); } return; }
  let D; try { D = prep(img); } catch (e) { return; }
  const hex = cur.hex, cr = parseInt(hex.slice(1,3),16), cg = parseInt(hex.slice(3,5),16), cb = parseInt(hex.slice(5,7),16);
  if (!cv) { cv = document.createElement("canvas"); cv.className = "pc"; img.parentElement.appendChild(cv); }
  cv.hidden = false; cv.width = D.w; cv.height = D.h;
  const g = cv.getContext("2d"), out = g.createImageData(D.w, D.h), o = out.data, d = D.d;
  for (let i = 0, p = 0; i < D.m.length; i++, p += 4) {
    const k = D.m[i];
    if (k < 0.01) { o[p] = d[p]; o[p+1] = d[p+1]; o[p+2] = d[p+2]; o[p+3] = 255; continue; }
    const sh0 = D.L[i] / D.ref, sh = sh0 < 1 ? Math.pow(sh0, 1.7) : sh0, base = Math.min(sh, 1), hi = Math.max(0, Math.min(sh - 1, 0.35)) * 0.9;
    const r = cr * base + (255 - cr) * hi, gg = cg * base + (255 - cg) * hi, b = cb * base + (255 - cb) * hi;
    o[p] = d[p] + (r - d[p]) * k; o[p+1] = d[p+1] + (gg - d[p+1]) * k; o[p+2] = d[p+2] + (b - d[p+2]) * k; o[p+3] = 255;
  }
  g.putImageData(out, 0, 0);
}

/* ---------- 3D: одна панель по профилю (или ламели под дерево), вращение пальцем ---------- */
const has3d = !!(P.prof || P.wood || P.poly);
const isPanel = X.c === "panel" || X.c === "color";
let nPan = 1;                                   // панелей рядом (по умолчанию одна, «+» добавляет)
const fragLen = () => Math.min(X.l, 600);   // фрагмент 60 см — рельеф виден крупно; вся панель — в «моей стене»
/* «Моя стена»: размеры клиента → сколько панелей (как в расчёте на главной: колонки по ширине, куски по высоте, минус проёмы, плюс запас) */
const wall = { W: 320, H: 270, open: 0, reserve: true, pcs: 0, used: false };
function wallCalc(){
  const Wcm = Math.max(0, +($("wW") || {}).value || 0), Hcm = Math.max(0, +($("wH") || {}).value || 0);
  wall.W = Wcm; wall.H = Hcm; wall.open = Math.max(0, +($("wO") || {}).value || 0); wall.reserve = !!($("wR") && $("wR").checked);
  const area = Wcm * Hcm / 10000, net = Math.max(0, area - wall.open);
  if (!Wcm || !Hcm) { wall.pcs = 0; return; }
  const cols = Math.ceil(Wcm * 10 / X.w), perCol = Math.ceil(Hcm * 10 / X.l);
  wall.pcs = Math.ceil(cols * perCol * (area ? net / area : 1) * (wall.reserve ? 1.1 : 1));
  wall.area = area; wall.net = net;
}
function renderWall(){
  wallCalc();
  if (!$("wPcs")) return;
  const n = wall.pcs, sum = n * price(), boxes = Math.floor(n / X.b), rest = n % X.b;
  $("wPcs").textContent = n ? `${n} шт` : "—";
  $("wPack").textContent = n ? (boxes ? `${boxes} кор.${rest ? " + " + rest + " шт" : ""}` : "поштучно") + ` · ${X.b} шт в коробке` : "укажите ширину и высоту";
  $("wSum").textContent = n && sum ? fmt(sum) + " ₽" : n ? "По запросу" : "—";
  $("wArea").textContent = n ? `стена ${wall.area.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} м², под отделку ${wall.net.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} м²` : "";
  if (n) { qty = n; wall.used = true; renderQty(); }
  updateLinks();
}
let view = has3d && !(isWood && P.photo) ? "frag" : "photo";   // под дерево — сначала фото, 3D по кнопке
const W3 = (() => {
  let R, S, cam, ctl, grp, mat, ready = false, inited = false, tex = null;
  const stage = $("pview"), cv = $("c3");
  function init(){
    if (inited) return; inited = true;
    if (!window.THREE || !THREE.OrbitControls || !cv) { if ($("nogl")) $("nogl").hidden = false; return; }
    try { R = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true }); }
    catch (e) { if ($("nogl")) $("nogl").hidden = false; return; }
    R.setPixelRatio(Math.min(devicePixelRatio, 2)); R.outputEncoding = THREE.sRGBEncoding; R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.2;
    R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap; R.localClippingEnabled = true;
    S = new THREE.Scene();
    cam = new THREE.PerspectiveCamera(35, 1, 5, 40000);
    ctl = new THREE.OrbitControls(cam, cv); ctl.enableDamping = true; ctl.enablePan = false; ctl.maxPolarAngle = Math.PI * 0.62;
    S.add(new THREE.HemisphereLight(0xffffff, 0xa89f93, 0.7));
    const sun = new THREE.DirectionalLight(0xfff6ea, 1.1); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0005; sun.shadow.normalBias = 2;
    S.add(sun); S.add(sun.target); S.userData.sun = sun;
    const fill = new THREE.DirectionalLight(0xdfe6f2, 0.35); fill.position.set(1, 0.6, -1); S.add(fill);
    new ResizeObserver(size).observe(stage); size();
    ready = true; build();
    (function loop(){ ctl.update(); R.render(S, cam); requestAnimationFrame(loop); })();
  }
  function size(){ if (!R) return; const r = stage.getBoundingClientRect(); if (!r.width) return; R.setSize(r.width, r.height, false); cam.aspect = r.width / Math.max(1, r.height); cam.updateProjectionMatrix(); }
  function profGeo(len){
    const pts = P.prof, sh = new THREE.Shape();
    sh.moveTo(0, 0); pts.forEach(p => sh.lineTo(p[0], p[1])); sh.lineTo(pts[pts.length-1][0], 0); sh.lineTo(0, 0);
    return new THREE.ExtrudeGeometry(sh, { depth: len, bevelEnabled: false, curveSegments: 1 });
  }
  /* Погонаж (молдинг, плинтус, карниз, уголок): контур сечения с отверстиями из каталога; кладём горизонтально:
     длина по X, высота изделия по Y (начало контура — верх), рельеф к зрителю (+Z) */
  function polyGeo(len){
    const W = P.poly.w, ring = r => r.map(p => new THREE.Vector2(W - p[0], p[1]));
    const sh = new THREE.Shape(ring(P.poly.outer));
    P.poly.holes.forEach(h => sh.holes.push(new THREE.Path(ring(h))));
    const g = new THREE.ExtrudeGeometry(sh, { depth: len, bevelEnabled: false, curveSegments: 1 });
    g.applyMatrix4(new THREE.Matrix4().set(0, 0, 1, 0,  1, 0, 0, 0,  0, 1, 0, 0,  0, 0, 0, 1));   // X←Z, Y←X, Z←Y
    return g;
  }
  const box = (x0, x1, y0, y1, len) => { const g = new THREE.BoxGeometry(x1 - x0, y1 - y0, len); g.translate((x0 + x1) / 2, (y0 + y1) / 2, len / 2); return g; };
  /* Панели стоят вертикально, как на стене (рельеф к зрителю, срез сверху — виден профиль);
     сзади светлая стена с тенью, свет скользит слева — рельеф читается. */
  function build(){
    if (!ready) return;
    if (grp) { S.remove(grp); grp.traverse(o => { if (o.geometry) o.geometry.dispose(); }); }
    grp = new THREE.Group(); S.add(grp);
    if (view === "wall") { buildWall(); return; }
    const len = view === "full" ? X.l : fragLen(), n = isPanel ? nPan : 1, W = X.w;
    const put = (me, c) => { me.rotation.x = Math.PI / 2; me.position.set(c * W, len, 0); me.castShadow = me.receiveShadow = true; grp.add(me); };
    if (P.poly) {
      mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(cur.hex).convertSRGBToLinear(), roughness: .6 });
      const me = new THREE.Mesh(polyGeo(len), mat); me.castShadow = me.receiveShadow = true; grp.add(me);
    } else if (P.wood) {
      if (!tex && P.tex) { tex = new THREE.TextureLoader().load(ROOT + P.tex); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.encoding = THREE.sRGBEncoding; }
      if (tex) tex.repeat.set(1, Math.max(1, len / 400));
      const blackM = new THREE.MeshStandardMaterial({ color: 0x141415, roughness: .7 });
      const woodM = new THREE.MeshStandardMaterial({ color: tex ? 0xffffff : 0x9a6a40, map: tex, roughness: .55 });
      const { base, slats } = P.wood;
      for (let c = 0; c < n; c++) {
        put(new THREE.Mesh(box(0, W, 0, base, len), blackM), c);
        slats.forEach(([a0, a1]) => put(new THREE.Mesh(box(a0, a1, base, X.t, len), woodM), c));
      }
    } else {
      mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(cur.hex).convertSRGBToLinear(), roughness: .6 });
      const g = profGeo(len);
      for (let c = 0; c < n; c++) put(new THREE.Mesh(g, mat), c);
    }
    // габарит сцены: панели стоят (ширина по X, длина по Y), погонаж лежит (длина по X, высота по Y)
    const bw = P.poly ? len : n * W, bh = P.poly ? W : len, big = Math.max(bw, bh) * 8 + 6000;
    // стена за изделием — принимает тень
    const wallM = new THREE.MeshStandardMaterial({ color: 0xe9e4db, roughness: .95 });
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(big, big), wallM);
    wall.position.set(bw / 2, bh / 2, -1.5); wall.receiveShadow = true; grp.add(wall);
    if (view === "full" && isPanel || X.c === "plinth") {   // пол: под панелью 3 м и под плинтусом
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(big, big), new THREE.MeshStandardMaterial({ color: 0xb79b7a, roughness: .85 }));
      floor.rotation.x = -Math.PI / 2; floor.position.set(bw / 2, 0, big / 2 - 2); floor.receiveShadow = true; grp.add(floor);
    }
    if (X.c === "cornice") {   // потолок над карнизом
      const ceil = new THREE.Mesh(new THREE.PlaneGeometry(big, big), new THREE.MeshBasicMaterial({ color: 0xf1ede6 }));
      ceil.rotation.x = Math.PI / 2; ceil.position.set(bw / 2, bh, big / 2 - 2); grp.add(ceil);
    }
    const sun = S.userData.sun, span = Math.max(bw, bh);
    sun.position.set(-span * 1.2, bh + span * 0.6, span * 0.9); sun.target.position.set(bw / 2, bh / 2, 0);
    Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 10, far: span * 6 }); sun.shadow.camera.updateProjectionMatrix();
    place(bh, bw);
  }
  /* Стена клиента: комната, панели рядами по ширине и высоте, обрезка по размерам стены (как на главной) */
  function buildWall(){
    wallCalc();
    const Wmm = Math.max(300, wall.W * 10), Hmm = Math.max(300, wall.H * 10), W = X.w;
    const clip = [new THREE.Plane(new THREE.Vector3(-1, 0, 0), Wmm), new THREE.Plane(new THREE.Vector3(0, -1, 0), Hmm)];
    const cols = Math.ceil(Wmm / W), rows = Math.ceil(Hmm / X.l);
    const wallM = new THREE.MeshStandardMaterial({ color: 0xe7e2d9, roughness: .95 });
    const back = new THREE.Mesh(new THREE.PlaneGeometry(Wmm + 1400, Hmm), wallM); back.position.set(Wmm / 2 + 500, Hmm / 2, -2); back.receiveShadow = true; grp.add(back);
    const side = new THREE.Mesh(new THREE.PlaneGeometry(14000, Hmm), wallM); side.rotation.y = Math.PI / 2; side.position.set(-2, Hmm / 2, 7000); side.receiveShadow = true; grp.add(side);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(Wmm + 8000, 14000), new THREE.MeshStandardMaterial({ color: 0xb79b7a, roughness: .8 }));
    floor.rotation.x = -Math.PI / 2; floor.position.set(Wmm / 2 + 3000, 0, 7000); floor.receiveShadow = true; grp.add(floor);
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(Wmm + 8000, 14000), new THREE.MeshBasicMaterial({ color: 0xefebe4 }));
    ceil.rotation.x = Math.PI / 2; ceil.position.set(Wmm / 2 + 3000, Hmm, 7000); grp.add(ceil);
    const put = (me, c, r) => { me.rotation.x = Math.PI / 2; me.position.set(c * W, (r + 1) * X.l, 0); me.castShadow = me.receiveShadow = true; grp.add(me); };
    if (P.wood) {
      if (!tex && P.tex) { tex = new THREE.TextureLoader().load(ROOT + P.tex); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.encoding = THREE.sRGBEncoding; }
      if (tex) tex.repeat.set(1, X.l / 400);
      const blackM = new THREE.MeshStandardMaterial({ color: 0x141415, roughness: .7, clippingPlanes: clip });
      const woodM = new THREE.MeshStandardMaterial({ color: tex ? 0xffffff : 0x9a6a40, map: tex, roughness: .55, clippingPlanes: clip });
      const { base, slats } = P.wood, gBase = box(0, W, 0, base, X.l), gSl = slats.map(([a0, a1]) => box(a0, a1, base, X.t, X.l));
      for (let c = 0; c < cols; c++) for (let r = 0; r < rows; r++) { put(new THREE.Mesh(gBase, blackM), c, r); gSl.forEach(g => put(new THREE.Mesh(g, woodM), c, r)); }
    } else {
      mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(cur.hex).convertSRGBToLinear(), roughness: .62, clippingPlanes: clip });
      const g = profGeo(X.l);
      for (let c = 0; c < cols; c++) for (let r = 0; r < rows; r++) put(new THREE.Mesh(g, mat), c, r);
    }
    if (Wmm > 2400) {   // диван для масштаба
      const sofaM = new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: .9 });
      const s1 = new THREE.Mesh(box(0, 2100, 0, 420, 900), sofaM), s2 = new THREE.Mesh(box(0, 2100, 0, 380, 200), sofaM);
      s1.position.set(Wmm / 2 - 1050, 0, 160); s2.position.set(Wmm / 2 - 1050, 420, 160);
      [s1, s2].forEach(m => { m.castShadow = m.receiveShadow = true; grp.add(m); });
    }
    const sun = S.userData.sun; sun.position.set(-Wmm * 0.4 - 2500, Hmm + 1200, 1100); sun.target.position.set(Wmm / 2, Hmm / 2, 0);
    const span = Math.max(Wmm, Hmm) * 0.9 + 1500;
    Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 100, far: 16000 }); sun.shadow.camera.updateProjectionMatrix();
    const d = Math.max(Wmm / (2 * Math.tan(20 * Math.PI / 180)) / Math.max(.6, cam.aspect), Hmm * 1.6) + 600;
    cam.position.set(Wmm * 0.62, Hmm * 0.5, d); ctl.target.set(Wmm / 2, Hmm * 0.45, 0); ctl.minDistance = 600; ctl.maxDistance = d * 3; ctl.update();
  }
  function place(len, width){
    if (P.poly) {   // погонаж лежит вдоль X: камера у ближнего (левого) торца, как на фото каталога — профиль крупно, длина уходит вглубь
      const W = X.w, T = P.poly.t, d = Math.max(W * 4.2, 130) + T;
      const tgt = new THREE.Vector3(Math.min(width * 0.4, d * 0.3), W / 2, T / 2);
      const dir = X.c === "cornice" ? new THREE.Vector3(-0.6, -0.35, 1) : new THREE.Vector3(-0.6, 0.45, 1);   // камера левее торца и спереди — виден и профиль, и рельеф
      dir.normalize(); cam.position.copy(dir.multiplyScalar(d)).add(tgt);
      ctl.target.copy(tgt); ctl.minDistance = W * 1.2; ctl.maxDistance = Math.max(width, W * 10) * 2; ctl.update(); return;
    }
    const cx = width / 2, cy = len / 2, r = Math.hypot(width, len) / 2;
    const d = r / Math.sin(cam.fov * Math.PI / 360) * (view === "full" ? 0.8 : width / len < 0.6 ? 1.0 : 0.9) / Math.min(1, cam.aspect / 1.15);   // одна панель выше, чем шире — дальше
    const dir = view === "full" ? new THREE.Vector3(0.55, 0.25, 1) : new THREE.Vector3(0.6, 0.45, 1);
    dir.normalize(); cam.position.copy(dir.multiplyScalar(d)).add(new THREE.Vector3(cx, cy, 0));
    ctl.target.set(cx, cy, 0); ctl.minDistance = r * 0.3; ctl.maxDistance = d * 3; ctl.update();
  }
  function setColor(hex){ if (mat) mat.color.set(hex).convertSRGBToLinear(); }
  return { init, rebuild: build, setColor: has3d && !P.wood ? setColor : null };
})();

/* ---------- вкладки: фрагмент / вся панель / фото ---------- */
function setView(v){
  view = v;
  document.querySelectorAll("[data-v]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
  const pv = $("pview"); pv.classList.toggle("is3d", v !== "photo");
  if ($("c3")) $("c3").hidden = v === "photo";
  if ($("photo")) $("photo").hidden = v !== "photo";
  const pc = pv.querySelector("canvas.pc"); if (pc) pc.hidden = v !== "photo" || cur.name === "Белый";
  if ($("hint")) $("hint").textContent = v === "photo" ? "" : v === "frag" ? `Фрагмент ${Math.round(fragLen() / 10)} см · вращайте пальцем` : "Вращайте пальцем, щипок — масштаб";
  if ($("wallBox")) $("wallBox").hidden = v !== "wall";
  const nc = document.querySelector(".ncount"); if (nc) nc.hidden = v !== "frag";
  if (v === "wall") renderWall();
  if (v === "photo") paintPhoto(); else { W3.init(); W3.rebuild(); hit("3d", X.a, v); }
}
["wW", "wH", "wO", "wR"].forEach(id => { if ($(id)) $(id).addEventListener("input", () => { renderWall(); W3.rebuild(); hit("calc", X.a); }); });
if ($("wOrder")) $("wOrder").addEventListener("click", () => { renderWall(); hit("item", X.a, "order"); $("order").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); setTimeout(() => $("lName").focus({ preventScroll: true }), 400); });
document.querySelectorAll("[data-v]").forEach(b => b.addEventListener("click", () => setView(b.dataset.v)));
function setN(n){ nPan = Math.max(1, Math.min(6, n)); if ($("nVal")) $("nVal").textContent = nPan; if (view !== "photo") W3.rebuild(); hit("3d", X.a, "n" + nPan); }
if ($("nMinus")) $("nMinus").addEventListener("click", () => setN(nPan - 1));
if ($("nPlus")) $("nPlus").addEventListener("click", () => { if (view === "photo") setView("frag"); setN(nPan + 1); });

/* ---------- количество и сумма ---------- */
function price(){ return X.r || 0; }
function renderQty(){
  $("qty").value = qty;
  const sum = qty * price(), boxes = Math.floor(qty / X.b), rest = qty % X.b;
  $("tSum").textContent = sum ? fmt(sum) + " ₽" : "По запросу";
  $("tPack").textContent = boxes ? `это ${boxes} кор.${rest ? " + " + rest + " шт" : ""} · в коробке ${X.b} шт` : `поштучно · в коробке ${X.b} шт`;
  if ($("oQty")) $("oQty").textContent = qty;
  if ($("oSum")) $("oSum").textContent = sum ? "≈ " + fmt(sum) + " ₽" : "цена по запросу";
}
$("qMinus").addEventListener("click", () => { qty = Math.max(1, qty - 1); renderQty(); });
$("qPlus").addEventListener("click", () => { qty = Math.min(9999, qty + 1); renderQty(); });
$("qBox").addEventListener("click", () => { qty = Math.max(X.b, Math.ceil(qty / X.b) * X.b); renderQty(); });
$("qty").addEventListener("input", () => { qty = Math.min(9999, Math.max(1, parseInt($("qty").value) || 1)); renderQty(); });

/* ---------- заявка или заказ на этот товар → CRM ---------- */
const LEAD_API = "https://crm.nashdekor.ru/api/lead";
let mode = "lead";                                   // lead — узнать цену/срок; buy — оформить заказ; call — перезвоните
const BTN = { lead: "Отправить заявку", buy: "Отправить заказ", call: "Заказать звонок" };
function setMode(m){
  mode = m === "buy" || m === "call" ? m : "lead";
  const buy = mode === "buy", call = mode === "call";
  document.querySelectorAll("#oMode [data-m]").forEach(b => { const on = b.dataset.m === mode; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
  $("oTitle").textContent = buy ? "Заказ" : call ? "Обратный звонок" : "Заявка";
  $("oNote").hidden = buy || call; $("oNoteBuy").hidden = !buy; $("oNoteCall").hidden = !call;
  $("oShip").hidden = !buy; $("lOferta").hidden = !buy;
  $("fEmail").hidden = call; $("fWho").hidden = call;
  $("lEmailHint").textContent = buy ? "пришлём подтверждение заказа и ссылку на оплату" : "пришлём расчёт письмом (необязательно)";
  $("lContact").placeholder = call ? "+7 …" : "+7 … или @ник"; $("lContactLbl").textContent = call ? "Телефон" : "Телефон или мессенджер";
  $("lMsg").placeholder = buy ? "Удобное время доставки, этаж, домофон, пожелания" : call ? "Когда удобно принять звонок" : "Адрес, сроки, нужна ли доставка";
  if (!$("leadForm").classList.contains("sent")) $("lSend").textContent = BTN[mode];
  $("leadForm").classList.toggle("buy", buy);
  shipUI();
}
function shipUI(){ const d = document.querySelector('input[name="ship"]:checked'); const pick = d && d.value === "pickup"; $("lAddr").hidden = pick; $("lAddr").required = mode === "buy" && !pick; }
document.querySelectorAll("#oMode [data-m]").forEach(b => b.addEventListener("click", () => { setMode(b.dataset.m); hit("item", X.a, "ask"); }));
document.querySelectorAll('input[name="ship"]').forEach(r => r.addEventListener("change", shipUI));
const WHO = {"Дизайнер": "designer", "Компания, объект": "company", "Ремонтная бригада": "company"};
const SHOP = P.shop || {};
const MSG = () => SHOP.max ? `MAX ${SHOP.max}` : "чат на сайте";   // личный Telegram с сайта убран
function orderText(){
  const sum = qty * price();
  const w = wall.used && wall.pcs === qty && wall.W && wall.H ? `\nСтена ${wall.W}×${wall.H} см${wall.open ? ", проёмы " + wall.open + " м²" : ""}${wall.reserve ? ", запас 10%" : ""}` : "";
  return `Товар: ${X.a} (${P.kind.toLowerCase()}) — ${qty} шт, ${isWood ? "декор" : "цвет"}: ${colorText()}${w}${sum ? `\nИтого ≈ ${fmt(sum)} ₽ (предварительно)` : ""}`;
}
async function sendLead(lead){
  if (!ON_SITE) return false;
  const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 12000);
  try {
    const r = await fetch(LEAD_API, { method: "POST", mode: "cors", credentials: "omit", signal: ctl.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: lead.name, contact: lead.contact, email: lead.email || "", who: WHO[lead.who] || "private",
        message: [lead.who && lead.who !== "Делаю ремонт у себя" ? "Кто: " + lead.who : "", lead.message].filter(Boolean).join("\n"),
        calc: lead.calc, total: lead.total, consent: true, consentAt: lead.consentAt, consentVersion: lead.consentVersion,
        intent: lead.intent || "lead", address: lead.address || "",
        website: ($("lHp") || {}).value || "" }) });
    const j = await r.json().catch(() => ({}));
    return r.ok && j.ok === true;
  } finally { clearTimeout(timer); }
}
async function copy(text, btn){
  try { await navigator.clipboard.writeText(text); btn.textContent = "Скопировано"; }
  catch (e) { btn.textContent = "Выделите и скопируйте"; }
  setTimeout(() => btn.textContent = "Копировать заявку", 1800);
}
$("leadForm").addEventListener("submit", async e => {
  e.preventDefault();
  const name = $("lName").value.trim(), contact = $("lContact").value.trim(), err = $("lErr");
  if (!name || !contact) { err.textContent = "Укажите имя и телефон или ник в мессенджере — по ним мы ответим."; err.hidden = false; return; }
  if (!$("lAgree").checked) { err.textContent = mode === "buy" ? "Отметьте согласие на обработку данных и условия продажи." : "Отметьте согласие на обработку персональных данных."; err.hidden = false; return; }
  const buy = mode === "buy", call = mode === "call";
  const pickup = buy && (document.querySelector('input[name="ship"]:checked') || {}).value === "pickup";
  const addr = buy ? (pickup ? "Самовывоз, СПб" : $("lAddr").value.trim()) : "";
  if (buy && !pickup && !addr) { err.textContent = "Укажите адрес доставки или выберите самовывоз."; err.hidden = false; $("lAddr").focus(); return; }
  err.hidden = true;
  const now = new Date().toISOString();
  const lead = { name, contact, email: ($("lEmail") ? $("lEmail").value.trim() : ""), who: $("lWho").value, message: $("lMsg").value.trim(), calc: orderText(), total: Math.round(qty * price()), consentAt: now, consentVersion: "2026-10-29", intent: mode, address: addr };
  const btn = $("lSend"); btn.disabled = true; btn.textContent = "Отправляем…";
  let saved = false; try { saved = await sendLead(lead); } catch (x) { saved = false; }
  btn.disabled = false; btn.textContent = BTN[mode];
  const text = `${buy ? "Заказ" : call ? "Перезвоните" : "Заявка"}: ${name}, ${contact}${lead.email ? ", " + lead.email : ""} (${lead.who})${addr ? "\nДоставка: " + addr : ""}${lead.message ? "\n" + lead.message : ""}\n${lead.calc}`;
  const done = $("lDone"); done.hidden = false;
  if (saved) {
    const next = buy
      ? `Менеджер проверит наличие, посчитает доставку и пришлёт ссылку на оплату${lead.email ? " на " + lead.email : ""} в рабочее время. Оплата картой или через СБП, чек придёт на e-mail; компаниям — счёт.`
      : call ? "Перезвоним в рабочее время." : "Мы ответим с ценой и наличием в рабочее время.";
    done.innerHTML = `<div class="stack" style="gap:12px"><div class="ok" role="status"><b id="lThanks"></b>${next}<p>Свяжемся с вами:<br><span id="lTo" style="white-space:nowrap;font-weight:600"></span></p><p>Если в номере ошибка — отправьте ещё раз или напишите нам в ${MSG()}.</p></div><button class="btn ghost" type="button" id="lAgain">${buy ? "Оформить ещё один заказ" : "Отправить ещё одну заявку"}</button></div>`;
    $("lThanks").textContent = buy ? `Спасибо, ${name}! Заказ принят. ` : call ? `Спасибо, ${name}! Заявка на звонок принята. ` : `Спасибо, ${name}! Заявка отправлена. `; $("lTo").textContent = contact;
    $("lAgain").onclick = () => { $("leadForm").classList.remove("sent"); $("leadForm").reset(); done.hidden = true; done.innerHTML = ""; setMode(mode); $("lName").focus(); };
    $("leadForm").reset(); $("leadForm").classList.add("sent");
    done.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    hit("lead", X.a, buy ? "buy" : ""); hitSend();
  } else {
    hit("leadfail", X.a);
    done.innerHTML = `<div class="stack" style="gap:8px"><div class="err">Форма сейчас не отправляется. Скопируйте текст заявки и пришлите его в ${MSG()}.</div><pre class="copy" id="lText"></pre><button class="btn sm" type="button" id="lCopy">Копировать заявку</button></div>`;
    $("lText").textContent = text; $("lCopy").onclick = ev => copy(text, ev.currentTarget);
  }
});
function goOrder(m){ setMode(m); hit("item", X.a, "ask"); $("order").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); setTimeout(() => $("lName").focus({ preventScroll: true }), 400); }
$("toOrder").addEventListener("click", () => goOrder("lead"));
if ($("toBuy")) $("toBuy").addEventListener("click", () => goOrder("buy"));
if (location.hash === "#buy" || location.hash === "#call") setMode(location.hash.slice(1));
if ($("toCalc")) $("toCalc").addEventListener("click", () => hit("item", X.a, "use"));
$("leadForm").addEventListener("focusin", () => hit("form", X.a));
if ($("c3")) $("c3").addEventListener("pointerdown", () => hit("3d", X.a, "rotate"), { passive: true });

/* ---------- запуск ---------- */
renderDots(); renderQty(); updateLinks(); setView(view);
loadCatalog().then(items => {
  const k = items && items[X.a]; if (!k) return;
  if (k.p > 0) X.r = k.p;
  const q = Math.max(0, k.q | 0);
  $("price").textContent = X.r ? fmt(X.r) + " ₽" : "По запросу";
  const st = $("stock"); st.textContent = stockText(q); st.classList.toggle("ok", q > 0);
  renderQty(); if (view === "wall") renderWall();
});
})();

/* строка разделов: текущий раздел виден в строке, тень, когда строка «прилипла» */
(() => { const sn = document.querySelector("nav.sections"); if (!sn) return;
  const on = sn.querySelector('[aria-current="page"]'); if (on) sn.scrollLeft = Math.max(0, on.offsetLeft - 16);
  let raf = 0;
  addEventListener("scroll", () => { if (raf) return; raf = requestAnimationFrame(() => { raf = 0;
    sn.classList.toggle("stuck", sn.getBoundingClientRect().top <= 62.5 && scrollY > 80); }); }, { passive: true }); })();
