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
"""

STAGE = """  <div class="ist" id="stage" tabindex="0" aria-roledescription="карусель" aria-label="Панель в интерьере">
    <canvas id="iv" width="1350" height="900"></canvas>
    <div class="ivtag" id="ivTag"></div>
    <div class="ivcap"><div><span id="ivCap"></span><small>3D-визуализация</small></div><div class="ivnum" id="ivNum"></div></div>
    <button type="button" class="ivnav" data-ivstep="-1" aria-label="Предыдущий кадр">‹</button><button type="button" class="ivnav" data-ivstep="1" aria-label="Следующий кадр">›</button>
  </div>
  <div class="ith" id="ivStrip" role="group" aria-label="Кадры: панель в интерьере"></div>
"""

HEAD_OLD = '<h2>Расчёт реечных панелей на стену в 3D</h2><p>Калькулятор: укажите размеры стены, выберите панель и цвет — стена перестроится, а ниже посчитаются штуки, коробки и сумма. Можно добавить плинтус и потолочный плинтус. Расчёт уйдёт вместе с заявкой.</p>'
HEAD_NEW = '<h2>Реечные панели в интерьере и расчёт на стену</h2><p>Нажмите на панель — она встанет на стену в кадре; кадр листается в сторону. Ниже калькулятор: укажите размеры стены — посчитаются штуки, коробки и сумма. Можно добавить плинтус и потолочный плинтус. Расчёт уйдёт вместе с заявкой.</p>'

JS = r"""/* Панель в интерьере: кадр-карусель над расчётом. Панель и цвет — из расчёта (выбор панели, кружки покраски).
   Кадры — 3D-визуализации img/int/<сцена>/<артикул>.jpg, уменьшенные — …/t/…, у каждой сцены mask.png (где на кадре панели) —
   по ней белая панель красится в выбранный цвет. Какие сцены и панели готовы — img/int/manifest.json. */
const IV = (() => {
  // кадры по комнатам, сначала крупный план: [сцена, подпись, комната]
  const SL = [["tvd", "ТВ-зона — крупно", "tv"], ["tv", "ТВ-зона — вся стена", "tv"], ["tv1", "ТВ-зона — полоса за экраном", "tv"], ["tv2", "ТВ-зона — две полосы", "tv"], ["tvc", "ТВ-зона — полоса с переходом на потолок", "tv"],
    ["sofad", "У дивана — крупно", "sofa"], ["sofa", "За диваном — вся стена", "sofa"], ["sofa1", "За диваном — одна полоса", "sofa"], ["sofa2", "За диваном — две полосы и полка", "sofa"],
    ["bedd", "Спальня — крупно", "bed"], ["bed", "Спальня — вся стена", "bed"], ["bed1", "Спальня — полоса за кроватью", "bed"],
    ["halld", "Прихожая — крупно", "hall"], ["hall", "Прихожая — вся стена", "hall"], ["half", "Прихожая — панели до середины стены", "hall"],
    ["deskd", "Рабочее место — крупно", "desk"], ["desk", "Рабочее место — вся стена", "desk"],
    ["cord", "Коридор — крупно", "cor"], ["cl", "Рельеф крупно", "cl"]];
  const BASE = [239, 238, 234];                              // белая краска, в которой посчитаны кадры (#EFEEEA)
  const st = $("stage"), cv = $("iv"), strip = $("ivStrip"), cache = {}, ready = new Set();
  let INT = null, V = "", cur = "", at = 0, seq = 0;
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
  st.addEventListener("click", e => { const b = e.target.closest("[data-ivstep]"); if (b) step(+b.dataset.ivstep); });
  strip.addEventListener("click", e => { const b = e.target.closest("[data-ivgo]"); if (b) { at = +b.dataset.ivgo; show(); } });
  st.addEventListener("keydown", e => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); step(e.key === "ArrowRight" ? 1 : -1); } });
  let t0 = null;
  st.addEventListener("touchstart", e => { t0 = e.touches.length === 1 ? [e.touches[0].clientX, e.touches[0].clientY] : null; }, { passive: true });
  st.addEventListener("touchend", e => { if (!t0) return; const dx = e.changedTouches[0].clientX - t0[0], dy = e.changedTouches[0].clientY - t0[1]; t0 = null; if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.3) step(dx < 0 ? 1 : -1); }, { passive: true });
  fetch("img/int/manifest.json", { cache: "no-cache" }).then(r => r.json()).then(m => { INT = m.scenes || {}; V = m.v || ""; update(); })
    .catch(() => { st.hidden = true; strip.hidden = true; });  // кадры не загрузились — расчёт ниже работает как обычно
  return { update };
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
