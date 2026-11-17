#!/usr/bin/env python3
"""Главная: вместо 3D-стены над расчётом — карусель «панель в интерьере» (кадры img/int, см. make_int_photos.py).

  python3 nashdekor-build/make_glavnaya_int.py           проба: 0f7s1eez/vizual/glavnaya/index.html — копия главной с заменой
                                                          (noindex, <base href="/">, счётчик посещений выключен); главная не меняется
  python3 nashdekor-build/make_glavnaya_int.py --apply   перенос: та же замена в самой 0f7s1eez/index.html

Каждая замена обязана найти своё место ровно один раз — если главная изменилась, скрипт останавливается с ошибкой и ничего не пишет.
Откат переноса — git revert коммита с --apply."""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '0f7s1eez')
SRC = os.path.join(ROOT, 'index.html')

CSS = """.ist{position:relative;aspect-ratio:3/2;width:min(100%,calc(min(52vh,560px)*1.5));margin:0 auto 8px;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:#23262d center/cover no-repeat;touch-action:pan-y;user-select:none;-webkit-user-select:none}
.ist canvas{position:absolute;inset:0;width:100%;height:100%;display:block;transition:opacity .18s}
.ist .ivnav{position:absolute;top:50%;width:44px;height:44px;margin-top:-22px;border:0;border-radius:50%;background:rgba(251,250,247,.9);color:#1E1D1B;font-size:26px;line-height:1;padding:0;display:grid;place-items:center;box-shadow:0 1px 6px rgba(0,0,0,.25)}
.ist .ivnav[data-ivstep="-1"]{left:8px}.ist .ivnav[data-ivstep="1"]{right:8px}
.ist .ivtag{position:absolute;left:8px;top:8px;background:rgba(251,250,247,.92);color:#1E1D1B;border-radius:999px;padding:3px 11px;font-size:13px;font-weight:600}
.ist .ivtag:empty{display:none}
.ist .ivcap{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:space-between;align-items:flex-end;gap:10px;padding:26px 12px 9px;color:#fff;font-size:14px;line-height:1.25;background:linear-gradient(transparent,rgba(0,0,0,.62));pointer-events:none}
.ist .ivcap small{display:block;font-size:11px;opacity:.8}
.ist .ivcap .ivnum{font-variant-numeric:tabular-nums;white-space:nowrap;font-size:13px}
.ith{display:flex;gap:6px;overflow-x:auto;width:min(100%,calc(min(52vh,560px)*1.5));margin:0 auto 16px;padding:0 0 4px;scrollbar-width:thin;-webkit-overflow-scrolling:touch}
.ith:empty{display:none}
.ith button{flex:0 0 auto;width:84px;padding:0;border:1px solid var(--line);border-radius:5px;overflow:hidden;background:#23262d;opacity:.72}
.ith button.gap{margin-left:8px}
.ith img{display:block;width:100%;height:auto;aspect-ratio:3/2}
.ith button[aria-current="true"]{opacity:1;border-color:var(--ink);box-shadow:0 0 0 1px var(--ink)}
.ist .ivfs{position:absolute;right:8px;top:8px;width:40px;height:40px;border:0;border-radius:50%;background:rgba(251,250,247,.9);color:#1E1D1B;padding:0;display:grid;place-items:center;box-shadow:0 1px 6px rgba(0,0,0,.25);cursor:pointer}
.ist{cursor:zoom-in}.ist button{cursor:pointer}
.ist .ivhint{display:none}
.ist.full{position:fixed!important;inset:0!important;z-index:2147483000;width:auto!important;height:auto!important;max-width:none;aspect-ratio:auto;margin:0!important;border:0;border-radius:0;box-shadow:none!important;background-color:#0d0e10;background-size:contain;touch-action:none;cursor:default}
.ist.full.zoomed{cursor:grab}
.ist.full canvas{object-fit:contain;transform-origin:0 0}
.ist.full .ivfs{top:calc(env(safe-area-inset-top,0px) + 10px);right:calc(env(safe-area-inset-right,0px) + 10px);width:48px;height:48px}
.ist.full .ivtag{top:calc(env(safe-area-inset-top,0px) + 18px);left:calc(env(safe-area-inset-left,0px) + 12px)}
.ist.full .ivnav[data-ivstep="-1"]{left:calc(env(safe-area-inset-left,0px) + 10px)}.ist.full .ivnav[data-ivstep="1"]{right:calc(env(safe-area-inset-right,0px) + 10px)}
.ist.full .ivcap{padding:40px calc(env(safe-area-inset-right,0px) + 14px) calc(env(safe-area-inset-bottom,0px) + 12px) calc(env(safe-area-inset-left,0px) + 14px)}
.ist.full.zoomed .ivnav,.ist.full.zoomed .ivcap{opacity:0;pointer-events:none}
.ist.full .ivhint{display:flex;flex-direction:column;align-items:center;gap:2px;position:absolute;left:50%;top:calc(env(safe-area-inset-top,0px) + 74px);transform:translateX(-50%);max-width:calc(100% - 28px);background:rgba(13,14,16,.78);color:#fff;font-size:13px;line-height:1.35;text-align:center;padding:7px 12px;border-radius:10px;pointer-events:none;opacity:0;transition:opacity .4s}
.ist.full .ivhint.on{opacity:1}
.ivhint .t,.ivhint .r{display:none}
@media (hover:none){.ivhint .t{display:block}.ivhint .m{display:none}}
@media (hover:none) and (orientation:portrait){.ivhint .r{display:block}}
html.ivfull,html.ivfull body{overflow:hidden}
html.ivfull .ndc-btn,html.ivfull .ndc-panel{display:none!important}
"""

STAGE = """  <div class="ist" id="stage" tabindex="0" aria-roledescription="карусель" aria-label="Панель в интерьере">
    <canvas id="iv" width="1350" height="900"></canvas>
    <div class="ivtag" id="ivTag"></div>
    <div class="ivcap"><div><span id="ivCap"></span><small>3D-визуализация</small></div><div class="ivnum" id="ivNum"></div></div>
    <button type="button" class="ivfs" id="ivFs" aria-label="Во весь экран" title="Во весь экран"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-6.5 6.5M10 20H4v-6M4 20l6.5-6.5"/></svg></button>
    <div class="ivhint" id="ivHint"><span class="t">Два пальца или двойное касание — приблизить</span><span class="r">Поверните телефон — кадр станет крупнее</span><span class="m">Колесо мыши или двойной щелчок — приблизить · Esc — свернуть</span></div>
    <button type="button" class="ivnav" data-ivstep="-1" aria-label="Предыдущий кадр">‹</button><button type="button" class="ivnav" data-ivstep="1" aria-label="Следующий кадр">›</button>
  </div>
  <div class="ith" id="ivStrip" role="group" aria-label="Кадры: панель в интерьере"></div>
"""

HEAD_OLD = '<h2>Расчёт реечных панелей на стену в 3D</h2><p>Калькулятор: укажите размеры стены, выберите панель и цвет — стена перестроится, а ниже посчитаются штуки, коробки и сумма. Можно добавить плинтус и потолочный плинтус. Расчёт уйдёт вместе с заявкой.</p>'
HEAD_NEW = '<h2>Реечные панели в интерьере и расчёт на стену</h2><p>Нажмите на панель — она встанет на стену в кадре; кадр листается в сторону. Ниже калькулятор: укажите размеры стены — посчитаются штуки, коробки и сумма. Можно добавить плинтус и потолочный плинтус. Расчёт уйдёт вместе с заявкой.</p>'

JS = r"""/* Панель в интерьере: кадр-карусель над расчётом. Панель и цвет — из расчёта (выбор панели, кружки покраски).
   Кадры — 3D-визуализации img/int/<сцена>/<артикул>.jpg, уменьшенные — …/t/…, у каждой сцены mask.png (где на кадре панели) —
   по ней белая панель красится в выбранный цвет. Какие сцены и панели готовы — img/int/manifest.json.
   Во весь экран: кнопка со стрелками в углу или касание кадра; свернуть — та же кнопка, Esc или «назад» на телефоне.
   Внутри — два пальца, двойное касание, колесо мыши: приблизить; приближенный кадр двигается пальцем или мышью. */
const IV = (() => {
  // кадры по комнатам, сначала крупный план: [сцена, подпись, комната]
  const SL = [["tvd", "ТВ-зона — крупно", "tv"], ["tv", "ТВ-зона — вся стена", "tv"], ["tv1", "ТВ-зона — полоса за экраном", "tv"], ["tv2", "ТВ-зона — две полосы", "tv"], ["tvc", "ТВ-зона — полоса с переходом на потолок", "tv"],
    ["sofad", "У дивана — крупно", "sofa"], ["sofa", "За диваном — вся стена", "sofa"], ["sofa1", "За диваном — одна полоса", "sofa"], ["sofa2", "За диваном — две полосы и полка", "sofa"],
    ["bedd", "Спальня — крупно", "bed"], ["bed", "Спальня — вся стена", "bed"], ["bed1", "Спальня — полоса за кроватью", "bed"],
    ["halld", "Прихожая — крупно", "hall"], ["hall", "Прихожая — вся стена", "hall"], ["half", "Прихожая — панели до середины стены", "hall"],
    ["deskd", "Рабочее место — крупно", "desk"], ["desk", "Рабочее место — вся стена", "desk"],
    ["cord", "Коридор — крупно", "cor"], ["cl", "Рельеф крупно", "cl"]];
  const BASE = [239, 238, 234];                              // белая краска, в которой посчитаны кадры (#EFEEEA)
  const EXP = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-6.5 6.5M10 20H4v-6M4 20l6.5-6.5"/></svg>', COL = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 4l-6 6M14 5v5h5M4 20l6-6M10 19v-5H5"/></svg>';
  const st = $("stage"), cv = $("iv"), strip = $("ivStrip"), fs = $("ivFs"), hint = $("ivHint"), cache = {}, ready = new Set();
  let INT = null, V = "", cur = "", at = 0, seq = 0, shown = "";
  const load = src => cache[src] || (cache[src] = new Promise((ok, no) => { const i = new Image(); i.onload = () => { ready.add(src); ok(i); }; i.onerror = no; i.src = src; }));
  const slides = a => INT ? SL.filter(([s]) => INT[s] && INT[s].includes(slug(a))) : [];
  const url = (s, a, small) => `img/int/${s}/${small ? "t/" : ""}${slug(a)}.jpg?v=${V}`, maskUrl = s => `img/int/${s}/mask.png?v=${V}`;
  const tintOf = a => { const p = paint[a]; return byA[a].c === "panel" && p && /^#[0-9a-f]{6}$/i.test(p.hex) && p.hex.toUpperCase() !== WHITE.toUpperCase() ? p : null; };
  function drawStrip(){
    const list = slides(cur);
    strip.innerHTML = list.map(([s, cap, room], i) => `<button type="button" data-ivgo="${i}"${i && room !== list[i - 1][2] ? ' class="gap"' : ""} aria-label="${cap}" title="${cap}"><img src="${url(s, cur, 1)}" alt="" loading="lazy" width="450" height="300"></button>`).join("");
  }
  async function show(){
    const list = slides(cur), x = byA[cur], g = cv.getContext("2d");
    st.querySelectorAll(".ivnav").forEach(b => { b.hidden = list.length < 2; });
    if (!list.length) { ++seq; cv.style.opacity = 0; st.style.backgroundImage = ""; $("ivTag").textContent = ""; $("ivNum").textContent = ""; $("ivCap").textContent = INT ? `Для ${cur} кадров в интерьере пока нет` : ""; return; }
    at = (at % list.length + list.length) % list.length;
    const [s, cap] = list[at], me = ++seq, src = url(s, cur), tint = tintOf(cur);
    if (shown !== s + cur) { shown = s + cur; resetZoom(); }  // другой кадр — снова целиком
    $("ivCap").textContent = cap; $("ivNum").textContent = `${at + 1} / ${list.length}`;
    $("ivTag").textContent = cur + " · " + (x.c === "color" ? decorName(x) : tint ? tint.name.toLowerCase() : "белая");
    strip.querySelectorAll("[data-ivgo]").forEach((b, i) => { b.setAttribute("aria-current", i === at); if (i === at) strip.scrollTo({ left: Math.max(0, b.offsetLeft - strip.offsetLeft - strip.clientWidth / 2 + 42), behavior: "smooth" }); });
    if (!ready.has(src) || (tint && !ready.has(maskUrl(s)))) { st.style.backgroundImage = `url(${url(s, cur, 1)})`; cv.style.opacity = 0; }
    try {
      const [img, mask] = await Promise.all([load(src), tint ? load(maskUrl(s)) : null]);
      if (me !== seq) return;
      const w = img.naturalWidth, h = img.naturalHeight; if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
      g.globalCompositeOperation = "source-over"; g.drawImage(img, 0, 0);
      if (mask) {                                            // покраска: кадр × (цвет / белый кадра), только по панелям
        const o = document.createElement("canvas"); o.width = w; o.height = h; const q = o.getContext("2d");
        q.fillStyle = `rgb(${[1, 3, 5].map((p, i) => Math.min(255, Math.round(parseInt(tint.hex.slice(p, p + 2), 16) / BASE[i] * 255)))})`; q.fillRect(0, 0, w, h);
        q.globalCompositeOperation = "destination-in"; q.drawImage(mask, 0, 0, w, h);
        g.globalCompositeOperation = "multiply"; g.drawImage(o, 0, 0); g.globalCompositeOperation = "source-over";
      }
      cv.style.opacity = 1;
      [1, -1].forEach(d => { const nx = list[(at + d + list.length) % list.length]; load(url(nx[0], cur)).catch(() => {}); if (tint) load(maskUrl(nx[0])).catch(() => {}); });
    } catch (e) { if (me === seq) cv.style.opacity = 0; }
  }
  function update(){                                         // из расчёта: сменилась панель или цвет
    const a = $("cPanel").value; if (!INT || !byA[a]) return;
    if (a !== cur) {                                         // при смене панели остаёмся в той же комнате
      const keep = cur && slides(cur)[at] ? slides(cur)[at][0] : null; cur = a;
      const i = slides(a).findIndex(([s]) => s === keep); at = i < 0 ? 0 : i; drawStrip();
    }
    show();
  }
  const step = d => { at += d; show(); };

  /* во весь экран и приближение */
  let full = false, real = false, openedAt = 0, z = 1, tx = 0, ty = 0, hintT = 0;
  const rel = p => { const r = st.getBoundingClientRect(); return [p.clientX - r.left, p.clientY - r.top]; };
  function clamp(){                                          // кадр не уезжает за край; меньше экрана — по центру
    if (z <= 1.001) { z = 1; tx = 0; ty = 0; }
    else {
      const W = st.clientWidth, H = st.clientHeight, iw = Math.min(W, H * 1.5), ih = iw / 1.5, ox = (W - iw) / 2, oy = (H - ih) / 2;
      const fit = (t, S, o, s) => s * z <= S ? S / 2 - (o + s / 2) * z : Math.min(-o * z, Math.max(S - (o + s) * z, t));
      tx = fit(tx, W, ox, iw); ty = fit(ty, H, oy, ih);
    }
    cv.style.transform = z === 1 ? "" : `translate(${tx}px,${ty}px) scale(${z})`;
    st.classList.toggle("zoomed", z > 1);
  }
  function zoomAt(nz, px, py){ nz = Math.max(1, Math.min(4, nz)); tx = px - (px - tx) / z * nz; ty = py - (py - ty) / z * nz; z = nz; clamp(); }
  function resetZoom(){ z = 1; clamp(); }
  function open(){
    if (full) return;
    full = true; real = false; openedAt = Date.now();
    st.classList.add("full"); document.documentElement.classList.add("ivfull");
    fs.innerHTML = COL; fs.setAttribute("aria-label", "Свернуть"); fs.title = "Свернуть";
    if (document.fullscreenEnabled && st.requestFullscreen) {            // Android, компьютер — настоящий полный экран
      real = true; st.requestFullscreen({ navigationUI: "hide" }).catch(() => { real = false; if (full) history.pushState({ ivf: 1 }, ""); });
    } else history.pushState({ ivf: 1 }, "");                           // iPhone: окно поверх страницы, «назад» сворачивает
    resetZoom(); hint.classList.add("on"); clearTimeout(hintT); hintT = setTimeout(() => hint.classList.remove("on"), 3500);
    st.focus({ preventScroll: true });
  }
  function done(){
    if (!full) return;
    full = false; real = false;
    st.classList.remove("full"); document.documentElement.classList.remove("ivfull"); hint.classList.remove("on");
    fs.innerHTML = EXP; fs.setAttribute("aria-label", "Во весь экран"); fs.title = "Во весь экран";
    resetZoom();
  }
  function close(){
    if (!full) return;
    if (document.fullscreenElement) { document.exitFullscreen().catch(done); return; }
    if (history.state && history.state.ivf) { history.back(); return; }
    done();
  }
  document.addEventListener("fullscreenchange", () => { if (document.fullscreenElement === st) return; if (full && real) done(); });
  addEventListener("popstate", () => { if (full && !document.fullscreenElement) done(); });
  addEventListener("resize", () => { if (full) clamp(); });

  st.addEventListener("click", e => {
    const b = e.target.closest("button");
    if (b && b.dataset.ivstep) step(+b.dataset.ivstep);
    else if (b === fs) full ? close() : open();
    else if (!b && !full) open();
  });
  strip.addEventListener("click", e => { const b = e.target.closest("[data-ivgo]"); if (b) { at = +b.dataset.ivgo; show(); } });
  st.addEventListener("keydown", e => { if (full) return; if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); step(e.key === "ArrowRight" ? 1 : -1); } });
  document.addEventListener("keydown", e => {
    if (!full) return;
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); step(e.key === "ArrowRight" ? 1 : -1); }
  });
  st.addEventListener("dblclick", e => { if (!full || e.target.closest("button") || Date.now() - openedAt < 500) return; const p = rel(e); zoomAt(z > 1 ? 1 : 2.5, p[0], p[1]); });
  st.addEventListener("wheel", e => { if (!full) return; e.preventDefault(); const p = rel(e); zoomAt(z * Math.exp(-e.deltaY * 0.0022), p[0], p[1]); }, { passive: false });
  let md = null;
  st.addEventListener("mousedown", e => { if (full && z > 1 && !e.target.closest("button")) { md = { x: e.clientX, y: e.clientY, tx, ty }; e.preventDefault(); } });
  addEventListener("mousemove", e => { if (md) { tx = md.tx + e.clientX - md.x; ty = md.ty + e.clientY - md.y; clamp(); } });
  addEventListener("mouseup", () => { md = null; });

  // пальцы: в сторону — следующий кадр; во весь экран — два пальца и двойное касание приближают, приближенный кадр двигается
  let t0 = null, pin = null, pan = null, tapT = 0, tapX = 0, tapY = 0;
  st.addEventListener("touchstart", e => {
    if (e.touches.length === 2 && full) {
      const a = rel(e.touches[0]), b = rel(e.touches[1]);
      pin = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, z, cx: ((a[0] + b[0]) / 2 - tx) / z, cy: ((a[1] + b[1]) / 2 - ty) / z }; t0 = null; pan = null; return;
    }
    if (e.touches.length !== 1) { t0 = null; return; }
    const p = rel(e.touches[0]); t0 = [e.touches[0].clientX, e.touches[0].clientY];
    pan = full && z > 1 ? { x: p[0], y: p[1], tx, ty } : null;
  }, { passive: true });
  st.addEventListener("touchmove", e => {
    if (!full) return;
    if (pin && e.touches.length === 2) {
      e.preventDefault();
      const a = rel(e.touches[0]), b = rel(e.touches[1]), nz = Math.max(1, Math.min(4, pin.z * Math.hypot(a[0] - b[0], a[1] - b[1]) / pin.d));
      z = nz; tx = (a[0] + b[0]) / 2 - pin.cx * nz; ty = (a[1] + b[1]) / 2 - pin.cy * nz; clamp();
    } else if (pan && e.touches.length === 1) {
      e.preventDefault(); const p = rel(e.touches[0]); tx = pan.tx + p[0] - pan.x; ty = pan.ty + p[1] - pan.y; clamp();
    } else e.preventDefault();
  }, { passive: false });
  st.addEventListener("touchend", e => {
    if (pin) { if (e.touches.length < 2) { pin = null; t0 = null; pan = e.touches.length === 1 && z > 1 ? (p => ({ x: p[0], y: p[1], tx, ty }))(rel(e.touches[0])) : null; } return; }
    if (!t0) return;
    const c = e.changedTouches[0], dx = c.clientX - t0[0], dy = c.clientY - t0[1]; t0 = null;
    if (pan) { pan = null; if (Math.abs(dx) + Math.abs(dy) > 10) return; }
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.3) { if (z === 1) step(dx < 0 ? 1 : -1); return; }
    if (!full || Math.abs(dx) > 10 || Math.abs(dy) > 10 || e.target.closest("button")) return;
    const now = Date.now(), p = rel(c);
    if (now - tapT < 320 && Math.hypot(p[0] - tapX, p[1] - tapY) < 40) { e.preventDefault(); tapT = 0; zoomAt(z > 1 ? 1 : 2.5, p[0], p[1]); }
    else { tapT = now; tapX = p[0]; tapY = p[1]; }
  }, { passive: false });

  fetch("img/int/manifest.json", { cache: "no-cache" }).then(r => r.json()).then(m => { INT = m.scenes || {}; V = m.v || ""; update(); })
    .catch(() => { st.hidden = true; strip.hidden = true; });  // кадры не загрузились — расчёт ниже работает как обычно
  return { update, open, close };
})();
window.__iv = IV; IV.update();"""


def once(s, old, new, what):
    n = s.count(old)
    if n != 1:
        sys.exit(f'ОШИБКА: «{what}» найдено {n} раз (нужно 1) — главная изменилась, замену надо сверить')
    return s.replace(old, new)


def between(s, a, b, new, what):
    """Заменить кусок от начала a до конца b (оба включительно)."""
    if s.count(a) != 1 or s.count(b) < 1:
        sys.exit(f'ОШИБКА: границы «{what}» не найдены однозначно ({s.count(a)}, {s.count(b)})')
    i = s.index(a)
    j = s.index(b, i) + len(b)
    return s[:i] + new + s[j:]


def transform(s):
    s = once(s, '<script src="/mebel/_lib/three.min.js"></script>\n', '', 'подключение three.js')
    s = once(s, HEAD_OLD, HEAD_NEW, 'заголовок блока расчёта')
    s = between(s, '  <div class="stage3d" id="stage">', '<div class="nogl" id="nogl" hidden>3D не запускается в этом браузере. Расчёт ниже работает как обычно.</div>\n  </div>\n', STAGE, 'сцена 3D')
    # стили 3D-сцены (.stage3d, .views, .zoom, .hint…) остаются: из CSS главной build.py собирает assets/p.css — ими живёт 3D на страницах товаров
    s = once(s, '.stage3d.used .hint{opacity:0}\n', '.stage3d.used .hint{opacity:0}\n' + CSS, 'стили 3D-сцены')
    old = '  .stage3d{position:sticky;top:calc(env(safe-area-inset-top,0px) + var(--hdr,57px));z-index:4;height:40vh;min-height:250px;margin-bottom:12px;box-shadow:0 10px 18px -14px rgba(0,0,0,.5)}'
    s = once(s, old, old + '\n  .ist{position:sticky;top:calc(env(safe-area-inset-top,0px) + var(--hdr,57px));z-index:4;box-shadow:0 10px 18px -14px rgba(0,0,0,.5)}', 'прилипание сцены на телефоне')
    s = between(s, '/* 3D-стена: комната с акцентной стеной из выбранных панелей', 'window.__w3 = W3; W3.init();', JS, 'модуль 3D-стены')
    s = once(s, 'if (window.__w3) window.__w3.rebuild();', 'if (window.__iv) window.__iv.update();', 'вызов из расчёта')
    s = once(s, '$("c3").addEventListener("pointerdown", () => hit("3d"), { passive: true });',
             '$("stage").addEventListener("pointerdown", () => hit("3d"), { passive: true });   // «3d» — прежнее имя счётчика: теперь это кадр «в интерьере» над расчётом',
             'счётчик нажатий на 3D (работает только на nashdekor.ru)')
    for left in ('W3.', '__w3', 'id="c3"', '$("c3")', 'class="stage3d"', 'three.min'):
        if left in s:
            sys.exit(f'ОШИБКА: после замены остался след 3D-стены: {left}')
    return s


def proba(s):
    """Копия для просмотра: не в поиске, ссылки и картинки — от корня сайта, счётчик посещений выключен, якоря листают саму копию."""
    s = once(s, '<meta charset="utf-8">', '<meta charset="utf-8"><base href="/"><meta name="robots" content="noindex,nofollow">', 'meta charset')
    s = once(s, 'const hitOn = ', 'const hitOn = false && ', 'счётчик посещений')
    s = once(s, '<body>', '<body><div style="background:#26292E;color:#F8F8F6;font:13px/1.4 -apple-system,Segoe UI,Roboto,Arial,sans-serif;padding:6px 14px">Проба: главная с каруселью «в интерьере» вместо 3D-стены. На сайте пока прежняя главная.</div>', 'body')
    s = once(s, '</body>', '<script>document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest(\'a[href^="#"]\');if(!a)return;var t=document.getElementById(a.getAttribute("href").slice(1));e.preventDefault();if(t)t.scrollIntoView({behavior:"smooth"})},true)</script></body>', '/body')
    return s


src = open(SRC, encoding='utf-8').read()
if '--apply' in sys.argv:
    out = transform(src)
    open(SRC, 'w', encoding='utf-8').write(out)
    print('главная: 3D-стена заменена каруселью «в интерьере»', len(src), '→', len(out), 'знаков')
else:
    if 'window.__iv = IV' in src:
        sys.exit('главная уже с каруселью — проба не нужна')
    out = proba(transform(src))
    dst = os.path.join(ROOT, 'vizual', 'glavnaya')
    os.makedirs(dst, exist_ok=True)
    open(os.path.join(dst, 'index.html'), 'w', encoding='utf-8').write(out)
    print('проба: vizual/glavnaya/index.html', len(src), '→', len(out), 'знаков')
