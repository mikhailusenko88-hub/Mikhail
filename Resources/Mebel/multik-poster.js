/* «Мультики»: обложка-постер (с 15.11.2026, по просьбе Михаила). Наши герои крупно — основа картинки, главный предмет серии
   по своему правилу, фон — место первой сцены, надпись маленькая (дети ещё не читают). Каждого героя и вещь снимаем отдельно
   «как в кино» на ровном фоне (чёрном и сером — по разнице получаем прозрачность вместе с шерстью) и собираем по одной из схем.
   Схемы и сторона главного героя чередуются по номеру серии — соседние обложки разные.
   MKPoster.make(ep, lib) → { full: canvas с надписями, clean: без надписей }. Нужны MK, MK3D (3D готов), герои подготовлены. */
(function (global) {
  'use strict';
  const P = { W: 1280, H: 720, FONT: 'ui-rounded, "SF Pro Rounded", "Arial Rounded MT Bold", -apple-system, "DejaVu Sans", sans-serif' };
  const SKY = new Set(['moon', 'rainbow', 'star', 'sun', 'kite', 'balloon', 'plane', 'rocket']);
  const FLOAT = new Set(['boat']);
  const BIG = new Set(['tree', 'castle', 'door', 'tent', 'snowman']);
  const FLAT = new Set(['puddle']);
  const EMO = { laugh: 'happy', sleepy: 'happy', shy: 'happy', love: 'happy', wink: 'happy', sad: 'surprised', scared: 'surprised', angry: 'surprised', think: 'surprised' };
  const tick = () => new Promise(r => setTimeout(r, 0));

  P.question = function (ep) { const t = String(ep.title || '').replace(/\s*\(часть \d+\)\s*$/i, '').trim(); const m = t.match(/^[^?!]*[?!]+/); return (m ? m[0] : t).trim(); };
  P.heroes = function (ep, lib) { const cnt = {}, first = {}; let k = 0;
    for (const sc of ep.scenes || []) for (const st of sc.steps || []) if (st.who && st.who !== 'Р' && lib.characters[st.who]) { if (first[st.who] == null) first[st.who] = k++; if (st.say) cnt[st.who] = (cnt[st.who] || 0) + 1; }
    const hs = Object.keys(first).sort((a, b) => (cnt[b] || 0) - (cnt[a] || 0) || first[a] - first[b]);
    // герой сериала («Кот Барсик» → Барсик) всегда первый и самый крупный: по нему узнают канал
    const ser = String(ep.series || '').toLowerCase(), star = hs.find(id => { const n = String((lib.characters[id].spec || {}).name || '').toLowerCase(); return n.length > 2 && ser.includes(n); });
    return star ? [star].concat(hs.filter(x => x !== star)) : hs; };
  /** мордочка героя: его эмоция в первой сцене (смех и грусть — в «радость» и «удивление»: на обложке глаза открыты, лицо светлое) */
  P.emotions = function (ep, hs) { const out = {}, sc0 = (ep.scenes || [])[0] || {};
    for (const st of sc0.steps || []) if (st.who && st.emotion && out[st.who] == null) out[st.who] = EMO[st.emotion] || st.emotion;
    hs.forEach((id, i) => { if (!out[id] || !/^(happy|surprised)$/.test(out[id])) out[id] = i === 0 ? 'surprised' : (i % 2 ? 'happy' : 'surprised'); }); return out; };

  function canvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
  function draw3d(cv, tl, t) { const c = cv.getContext('2d'); c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height); c.setTransform(cv.width / 1920, 0, 0, cv.height / 1080, 0, 0); global.MK.render(c, tl, t - .1); global.MK.render(c, tl, t); c.setTransform(1, 0, 0, 1, 0, 0); }   // первый кадр — шерсть и свет устоялись

  /** прозрачность по двум кадрам: на чёрном фоне α·F, на сером α·F + (1-α)·B (серый после обработки неровный — меряем по клеткам) */
  P.matte = function (A, B) {
    const w = A.width, h = A.height, a = A.getContext('2d').getImageData(0, 0, w, h).data, b = B.getContext('2d').getImageData(0, 0, w, h).data;
    const GX = 16, GY = 9, sum = new Float32Array(GX * GY), cnt = new Float32Array(GX * GY);
    for (let y = 0; y < h; y += 3) for (let x = 0; x < w; x += 3) { const i = (y * w + x) * 4; if (Math.max(a[i], a[i + 1], a[i + 2]) < 3) { const k = Math.min(GY - 1, (y * GY / h) | 0) * GX + Math.min(GX - 1, (x * GX / w) | 0); sum[k] += (b[i] + b[i + 1] + b[i + 2]) / 3; cnt[k]++; } }
    let tot = 0, tn = 0; for (let k = 0; k < GX * GY; k++) { tot += sum[k]; tn += cnt[k]; }
    const g0 = tn ? tot / tn : 180, grid = new Float32Array(GX * GY);
    for (let k = 0; k < GX * GY; k++) grid[k] = cnt[k] > 20 ? sum[k] / cnt[k] : -1;
    for (let it = 0; it < 12; it++) for (let k = 0; k < GX * GY; k++) if (grid[k] < 0) { let s = 0, n = 0; const gx = k % GX, gy = (k / GX) | 0; for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const xx = gx + dx, yy = gy + dy; if (xx >= 0 && yy >= 0 && xx < GX && yy < GY && grid[yy * GX + xx] > 0) { s += grid[yy * GX + xx]; n++; } } if (n) grid[k] = s / n; }
    for (let k = 0; k < GX * GY; k++) if (grid[k] < 0) grid[k] = g0;
    const bgAt = (x, y) => { const fx = Math.max(0, Math.min(GX - 1.001, x * GX / w - .5)), fy = Math.max(0, Math.min(GY - 1.001, y * GY / h - .5)), x0 = fx | 0, y0 = fy | 0, tx = fx - x0, ty = fy - y0, x1 = Math.min(GX - 1, x0 + 1), y1 = Math.min(GY - 1, y0 + 1);
      return (grid[y0 * GX + x0] * (1 - tx) + grid[y0 * GX + x1] * tx) * (1 - ty) + (grid[y1 * GX + x0] * (1 - tx) + grid[y1 * GX + x1] * tx) * ty; };
    const out = new ImageData(w, h), o = out.data; let x0 = w, y0 = h, x1 = -1, y1 = -1;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = (y * w + x) * 4, mx = Math.max(a[i], a[i + 1], a[i + 2]);
      if (mx < 3) continue; const d = ((b[i] - a[i]) + (b[i + 1] - a[i + 1]) + (b[i + 2] - a[i + 2])) / 3; let al = 1 - d / Math.max(50, bgAt(x, y)); if (al < .04) continue; if (al > .96) al = 1;
      o[i] = Math.min(255, a[i] / al); o[i + 1] = Math.min(255, a[i + 1] / al); o[i + 2] = Math.min(255, a[i + 2] / al); o[i + 3] = al * 255;
      if (al > .3) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } }
    keepMain(o, w, h);
    if (x1 < 0) return null; const pad = 6; x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad); x1 = Math.min(w - 1, x1 + pad); y1 = Math.min(h - 1, y1 + pad);
    const full = canvas(w, h); full.getContext('2d').putImageData(out, 0, 0); const cut = canvas(x1 - x0 + 1, y1 - y0 + 1); cut.getContext('2d').drawImage(full, -x0, -y0);
    cut.cutBottom = y1 >= h - 1 - pad - 2; return cut; };   // герой обрезан кадром снизу — на обложке низ растушуем, если он не у края
  /** только самое большое пятно (без «!» удивления над головой и случайных крошек) — по уменьшенной маске */
  function keepMain(o, w, h) { const s = 4, W2 = Math.ceil(w / s), H2 = Math.ceil(h / s), m = new Uint8Array(W2 * H2), lab = new Int32Array(W2 * H2);
    for (let y = 0; y < h; y += s) for (let x = 0; x < w; x += s) if (o[(y * w + x) * 4 + 3] > 60) m[(y / s | 0) * W2 + (x / s | 0)] = 1;
    let best = 0, bestN = 0, cur = 0; const st = [];
    for (let k = 0; k < W2 * H2; k++) { if (!m[k] || lab[k]) continue; cur++; let n = 0; st.push(k); lab[k] = cur;
      while (st.length) { const q = st.pop(); n++; const qx = q % W2, qy = (q / W2) | 0; for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]]) { const xx = qx + dx, yy = qy + dy; if (xx < 0 || yy < 0 || xx >= W2 || yy >= H2) continue; const kk = yy * W2 + xx; if (m[kk] && !lab[kk]) { lab[kk] = cur; st.push(kk); } } }
      if (n > bestN) { bestN = n; best = cur; } }
    if (cur < 2) return;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = (y * w + x) * 4; if (!o[i + 3]) continue; let keep = false; const cx = (x / s) | 0, cy = (y / s) | 0;
      for (let dy = -2; dy <= 2 && !keep; dy++) for (let dx = -2; dx <= 2; dx++) { const xx = cx + dx, yy = cy + dy; if (xx >= 0 && yy >= 0 && xx < W2 && yy < H2 && lab[yy * W2 + xx] === best) { keep = true; break; } }
      if (!keep) o[i + 3] = 0; } }

  function studio(cv, draw) { const A = canvas(cv.width, cv.height), B = canvas(cv.width, cv.height), M3 = global.MK3D;
    try { M3._studio = '#000000'; draw(A); M3._studio = '#bfbfbf'; draw(B); } finally { M3._studio = null; } return P.matte(A, B); }

  function sceneEp(ep, scene) { return Object.assign({}, ep, { scenes: [scene], titleCard: false, endCard: false, subscribe: false, autoCam: false, main: false, mainSet: false, subtitles: false }); }
  function compile(ep, lib) { const tl = global.MK.compile(ep, Object.assign({}, lib, { settings: Object.assign({}, lib.settings, { opening: 'new', intro: 'none' }) }), {}); tl.style = '3d'; return tl; }

  /** герой крупно, мордочка живая: короткий возглас («Ура-а-а!» / «Ого-о-о!»), кадр — когда рот открыт (без звука рот движется по формуле — пик через 0,37 с) */
  P.heroCut = function (ep, lib, id, emo, loc, say, k) {
    const e2 = sceneEp(ep, { id: 'П1', location: loc, cast: [{ who: id, x: .5, face: 'camera' }], props: [], steps: [{ who: id, emotion: emo, say: say || (emo === 'happy' ? 'Ура-а-а!' : 'Ого-о-о!') }, { wait: 2 }], tail: 0 });
    const tl = compile(e2, lib), sg = tl.segs.find(x => x.kind === 'scene'); if (sg) sg.cam = [{ t: 0, mode: 'close', on: id, cut: true }];
    const sp = (tl.speech || []).find(x => x.who === id), t = sp ? sp.t + (k || .374) : 1.3;
    return studio(canvas(1280, 720), cv => draw3d(cv, tl, t)); };
  P.propCut = function (type) { return studio(canvas(900, 900), cv => { const c = cv.getContext('2d'); c.clearRect(0, 0, cv.width, cv.height); global.MK3D.propSheet(cv, [type], 1); }); };
  P.background = function (ep, lib, loc) {
    const e2 = sceneEp(ep, { id: 'П0', location: loc, cast: [], props: [], steps: [{ wait: 3 }], tail: 0 });
    const tl = compile(e2, lib), sg = tl.segs.find(x => x.kind === 'scene'); if (sg) sg.cam = [{ t: 0, mode: 'wide', cut: true }];
    const cv = canvas(1280, 720); draw3d(cv, tl, 1.0); return cv; };

  /** схемы: cx — центр героя, y — верх, h — высота (доли кадра). Порядок героев — по числу реплик (первый — главный). */
  const LAY = {
    side: { 5: [[.20, .17, .86], [.86, .20, .82], [.37, .10, .46], [.66, .04, .54], [.08, .58, .44]], 4: [[.20, .15, .88], [.84, .18, .84], [.38, .08, .50], [.64, .05, .54]], 3: [[.22, .12, .92], [.80, .16, .86], [.50, .03, .50]], 2: [[.24, .10, .95], [.78, .14, .88]], 1: [[.28, .08, .95]], back: [2, 3] },
    center: { 5: [[.50, .03, .78], [.15, .20, .80], [.85, .20, .80], [.31, .52, .50], [.69, .52, .50]], 4: [[.50, .03, .80], [.16, .18, .82], [.84, .18, .82], [.30, .52, .50]], 3: [[.50, .03, .82], [.17, .16, .84], [.83, .16, .84]], 2: [[.36, .05, .92], [.78, .12, .88]], 1: [[.32, .06, .95]], back: [0] },
  };
  function plan(n, kind, num) { const v = num % 3, name = n >= 3 && v === 2 ? 'center' : 'side', mir = v === 1; const L = LAY[name], pts = (L[Math.min(5, Math.max(1, n))] || L[1]).map(p => p.slice());
    let obj; if (kind === 'sky') { obj = { cx: .5, y: .02, h: .36, behind: true }; pts.forEach(p => { p[1] += .09; p[2] *= .9; }); }
    else if (kind === 'big') obj = { cx: .5, y: -.02, h: .9, behind: true };
    else if (kind === 'flat') obj = { cx: .45, bottom: .97, h: .2 };
    else if (kind === 'float') obj = { cx: n === 1 ? .72 : .5, bottom: name === 'center' ? .98 : .72, h: .56 };
    else obj = { cx: n === 1 ? .72 : .5, bottom: name === 'center' ? .99 : .78, h: .44, glow: true };
    if (mir) { pts.forEach(p => { p[0] = 1 - p[0]; }); obj.cx = 1 - obj.cx; }
    return { pts, obj, back: L.back, mir, name }; }

  function fadeBottom(im) { if (im._faded) return im._faded; const f = canvas(im.width, im.height), g = f.getContext('2d'); g.drawImage(im, 0, 0); g.globalCompositeOperation = 'destination-out';
    const gr = g.createLinearGradient(0, im.height * .8, 0, im.height); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,1)'); g.fillStyle = gr; g.fillRect(0, im.height * .8, im.width, im.height * .2); im._faded = f; return f; }
  function put(c, im, cx, y, h, opt) { if (!im) return; const H = P.H, W = P.W, hh = h * H, ww = im.width * hh / im.height, x = cx * W - ww / 2, yy = y * H; opt = opt || {};
    if (im.cutBottom && y + h < .97) im = fadeBottom(im);   // обрезанный низ посреди картинки — мягко растворяем
    c.save(); if (opt.flip) { c.translate(cx * W * 2, 0); c.scale(-1, 1); }
    c.shadowColor = 'rgba(0,0,0,.35)'; c.shadowBlur = 22; c.shadowOffsetX = 6; c.shadowOffsetY = 10; c.drawImage(im, x, yy, ww, hh);
    c.shadowColor = 'rgba(255,255,255,.9)'; c.shadowBlur = 12; c.shadowOffsetX = 0; c.shadowOffsetY = 0; c.drawImage(im, x, yy, ww, hh); c.restore(); return { x, y: yy, w: ww, h: hh }; }
  function ripples(c, cx, cy, w) { c.save(); c.translate(cx, cy); for (const [k, a] of [[1, .28], [.78, .38], [.56, .5]]) { c.beginPath(); c.ellipse(0, 0, w * k / 2, w * k * .11, 0, 0, Math.PI * 2); c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = Math.max(3, w * .012); c.stroke(); }
    c.beginPath(); c.ellipse(0, 0, w * .42, w * .07, 0, 0, Math.PI * 2); c.fillStyle = 'rgba(60,140,210,.45)'; c.fill(); c.restore(); }
  /** лужа: неровное пятно с небом внутри, блики и круги от капель */
  function puddle(c, cx, cy, w) { const h = w * .26; c.save(); c.translate(cx, cy - h * .55); c.beginPath();
    for (let i = 0; i <= 40; i++) { const a = i / 40 * Math.PI * 2, r = 1 + .09 * Math.sin(a * 3 + 1) + .06 * Math.sin(a * 5 + 2); const x = Math.cos(a) * w / 2 * r, y = Math.sin(a) * h / 2 * r; i ? c.lineTo(x, y) : c.moveTo(x, y); }
    c.closePath(); c.shadowColor = 'rgba(40,30,20,.35)'; c.shadowBlur = 14; c.shadowOffsetY = 4; const g = c.createLinearGradient(0, -h / 2, 0, h / 2); g.addColorStop(0, '#9fd8ff'); g.addColorStop(.6, '#4c9be0'); g.addColorStop(1, '#2f6fb8'); c.fillStyle = g; c.fill();
    c.shadowColor = 'transparent'; c.lineWidth = 5; c.strokeStyle = 'rgba(255,255,255,.85)'; c.stroke(); c.clip();
    for (const [x, y, k] of [[-.18, -.05, 1], [.2, .08, .7]]) for (const m of [1, .62]) { c.beginPath(); c.ellipse(x * w, y * h, w * .12 * k * m, h * .2 * k * m, 0, 0, Math.PI * 2); c.lineWidth = 3; c.strokeStyle = 'rgba(255,255,255,.7)'; c.stroke(); }
    c.beginPath(); c.ellipse(w * .14, -h * .22, w * .16, h * .07, -.1, 0, Math.PI * 2); c.fillStyle = 'rgba(255,255,255,.55)'; c.fill(); c.restore(); }
  function shine(c, cx, cy, r) { const g = c.createRadialGradient(cx, cy, 0, cx, cy, r); g.addColorStop(0, 'rgba(255,250,215,.95)'); g.addColorStop(.45, 'rgba(255,236,160,.55)'); g.addColorStop(1, 'rgba(255,236,160,0)'); c.fillStyle = g; c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.fill(); }

  function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
  /** надписи — маленькие: логотип сериала (как у канала) и «СЕРИЯ N» в верхних углах, вопрос — небольшой свиток в нижнем углу напротив главного героя */
  P.logo = function (c, series, x, y, k) { const F = P.FONT, ws = String(series || 'Мультик').trim().split(/\s+/), l1 = ws.length > 1 ? ws[0] : '', l2 = ws.length > 1 ? ws.slice(1).join(' ') : ws[0];
    c.save(); c.translate(x, y); c.rotate(-.06); c.scale(k, k); c.lineJoin = 'round'; c.textBaseline = 'alphabetic'; c.textAlign = 'left';
    const rows = [[l1, 52, 18, 58], [l2, 72, 4, 128]].filter(r => r[0]);
    const txt = (t, sz, tx, ty, fn) => { c.font = `900 ${sz}px ${F}`; fn(t, tx, ty, c.measureText(t).width); };
    c.shadowColor = 'rgba(60,30,10,.55)'; c.shadowBlur = 10; c.shadowOffsetX = 3; c.shadowOffsetY = 5;
    for (const [t, sz, tx, ty] of rows) txt(t, sz, tx, ty, () => { c.lineWidth = sz * .36; c.strokeStyle = '#ffffff'; c.strokeText(t, tx, ty); });
    c.shadowColor = 'transparent';
    for (const [t, sz, tx, ty] of rows) txt(t, sz, tx, ty, (t, tx, ty, w) => { c.lineWidth = sz * .15; c.strokeStyle = '#6e340e'; c.strokeText(t, tx, ty);
      const g = c.createLinearGradient(0, ty - sz * .8, 0, ty); g.addColorStop(0, '#ffe25c'); g.addColorStop(1, '#f68016'); c.fillStyle = g; c.fillText(t, tx, ty); });
    if (l1) { c.font = `900 52px ${F}`; const px = 18 + c.measureText(l1).width + 30, py = 30;   // лапка
      const toes = [[0, 10, 11], [-12, -5, 5.5], [-4, -13, 5.5], [6, -13, 5.5], [14, -5, 5.5]];
      for (const [dx, dy, r] of toes) { c.beginPath(); c.arc(px + dx, py + dy, r + 4, 0, Math.PI * 2); c.fillStyle = '#fff'; c.fill(); }
      for (const [dx, dy, r] of toes) { c.beginPath(); c.arc(px + dx, py + dy, r, 0, Math.PI * 2); c.fillStyle = '#f68016'; c.fill(); c.lineWidth = 2.5; c.strokeStyle = '#6e340e'; c.stroke(); } }
    c.restore(); };
  P.pill = function (c, text, xr, y) { const F = P.FONT, sz = 38; c.save(); c.font = `900 ${sz}px ${F}`; const tw = c.measureText(text).width, w = tw + 52, h = 64, x = xr - w;
    c.shadowColor = 'rgba(0,0,0,.4)'; c.shadowBlur = 10; c.shadowOffsetX = 3; c.shadowOffsetY = 6; c.fillStyle = '#fff'; rr(c, x, y, w, h, h / 2); c.fill(); c.shadowColor = 'transparent';
    const g = c.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, '#f04232'); g.addColorStop(.5, '#f04232'); g.addColorStop(.5, '#e2241e'); g.addColorStop(1, '#e2241e'); c.fillStyle = g; rr(c, x + 6, y + 6, w - 12, h - 12, (h - 12) / 2); c.fill();
    c.textAlign = 'center'; c.textBaseline = 'middle'; c.lineJoin = 'round'; c.lineWidth = 3; c.strokeStyle = '#96140f'; c.strokeText(text, x + w / 2, y + h / 2 + 2); c.fillStyle = '#fff'; c.fillText(text, x + w / 2, y + h / 2 + 2); c.restore(); };
  P.decorate = function (c, ep, side) { const W = P.W, H = P.H, F = P.FONT, q = P.question(ep).toUpperCase(); c.save(); c.lineJoin = 'round'; c.textAlign = 'center'; c.textBaseline = 'middle';
    P.logo(c, ep.series, 12, 10, .82);
    if (ep.episode) P.pill(c, 'СЕРИЯ ' + ep.episode, W - 22, 22);
    if (q) { const maxW = W * .30; let sz = 44, lines = [];
      const ws = q.split(/\s+/), split = () => { if (ws.length < 2) return [q]; let best = null;   // две строки поровну; короткий предлог («В», «НА») — на вторую строку
          for (let i = 1; i < ws.length; i++) { const a = ws.slice(0, i).join(' '), b = ws.slice(i).join(' '), m = Math.max(c.measureText(a).width, c.measureText(b).width) + (ws[i - 1].length <= 2 ? 1e4 : 0); if (!best || m < best.m) best = { m, l: [a, b] }; }
          return c.measureText(q).width <= maxW * .62 ? [q] : best.l; };
      for (; sz >= 28; sz -= 2) { c.font = `900 ${sz}px ${F}`; lines = split(); if (lines.every(l => c.measureText(l).width <= maxW)) break; }
      const lh = sz * 1.1, ph = lines.length * lh + 34, pw = Math.max(...lines.map(l => c.measureText(l).width)) + 80, px = side === 'left' ? 30 : W - pw - 30, py = H - ph - 22;
      c.shadowColor = 'rgba(0,0,0,.35)'; c.shadowBlur = 16; c.shadowOffsetY = 6; const g = c.createLinearGradient(0, py, 0, py + ph); g.addColorStop(0, '#fff6dc'); g.addColorStop(1, '#f1d394'); c.fillStyle = g; rr(c, px, py, pw, ph, 14); c.fill(); c.shadowColor = 'transparent'; c.lineWidth = 4; c.strokeStyle = '#a8742c'; c.stroke();
      for (const sd of [-1, 1]) { const rx = sd < 0 ? px - 10 : px + pw - 16, gr = c.createLinearGradient(rx, 0, rx + 26, 0); gr.addColorStop(0, '#c8954a'); gr.addColorStop(.5, '#f6dfa6'); gr.addColorStop(1, '#a8742c'); c.fillStyle = gr; rr(c, rx, py - 9, 26, ph + 18, 12); c.fill(); c.lineWidth = 3; c.strokeStyle = '#7a4f1c'; c.stroke(); }
      c.font = `900 ${sz}px ${F}`; lines.forEach((l, i) => { const y = py + 17 + lh * (i + .5) + 2; c.lineWidth = Math.max(6, sz * .14); c.strokeStyle = '#fff8e6'; c.strokeText(l, px + pw / 2, y); c.fillStyle = '#7a1c12'; c.fillText(l, px + pw / 2, y); }); }
    c.restore(); };

  /** главное: собрать обложку. prog(текст, доля) — чтобы показывать, что делается */
  P.make = async function (ep, lib, prog) {
    const MK = global.MK, sc0 = (ep.scenes || [])[0] || {}, loc = sc0.location, L = ((lib.locations || {})[loc] || {}).spec || {};
    const hs = P.heroes(ep, lib).slice(0, 5); if (!hs.length) throw new Error('в серии нет героев');
    const emo = P.emotions(ep, hs), M = MK.mainOf(ep, lib), type = M && M.type;
    const water = /^(beach|sea|river|lake)$/.test(L.type || '');
    const kind = !type ? null : SKY.has(type) ? 'sky' : FLAT.has(type) ? 'flat' : FLOAT.has(type) ? (water ? 'float' : 'small') : BIG.has(type) ? 'big' : 'small';
    const say = (t, k) => { if (prog) prog(t, k); };
    say('Фон', .05); await tick(); const bg = P.background(ep, lib, loc);
    const cuts = {}; for (let i = 0; i < hs.length; i++) { say('Герои ' + (i + 1) + ' из ' + hs.length, .1 + .6 * i / hs.length); await tick(); cuts[hs[i]] = P.heroCut(ep, lib, hs[i], emo[hs[i]], loc, i === 0 ? 'Вот это да!' : null, i === 0 ? .299 : null); }   // главному — рот приоткрыт (без «крика»)
    let obj = null; if (type && type !== 'puddle') { say('Главный предмет', .75); await tick(); obj = P.propCut(type); }   // лужу рисуем сами: в студии вода отражает серый фон
    say('Собираю', .9); await tick();
    const num = +ep.episode || 0, pl = plan(hs.length, kind, num), W = P.W, H = P.H, out = canvas(W, H), c = out.getContext('2d');
    // фон: у воды — верхняя часть кадра (видно море), иначе — весь; мягкое размытие, чтобы герои читались
    const sy = water ? 0 : 60, sh = water ? 540 : 660, sw = sh * 16 / 9, sx = (1280 - sw) / 2;
    c.save(); try { c.filter = 'blur(5px) saturate(1.15) brightness(1.04)'; } catch (e) {} c.drawImage(bg, sx, sy, sw, sh, -10, -10, W + 20, H + 20); c.restore();
    if (!('filter' in c)) { const t = canvas(W / 6, H / 6); t.getContext('2d').drawImage(out, 0, 0, t.width, t.height); c.drawImage(t, 0, 0, W, H); }
    const drawObj = () => { if (type === 'puddle') return puddle(c, pl.obj.cx * W, pl.obj.bottom * H, W * .42); if (!obj) return; const o = pl.obj, hh = o.h, y = o.y != null ? o.y : o.bottom - hh;
      if (kind === 'float') ripples(c, o.cx * W, (o.bottom - .02) * H, W * .34);
      if (kind === 'small' || kind === 'sky') shine(c, o.cx * W, (y + hh * .5) * H, hh * H * .75);
      put(c, obj, o.cx, y, hh); };
    const order = hs.map((id, i) => i); const back = order.filter(i => pl.back.includes(i)), front = order.filter(i => !pl.back.includes(i));
    if (pl.obj.behind) drawObj();
    for (const i of back) { const p = pl.pts[i]; if (p) put(c, cuts[hs[i]], p[0], p[1], p[2]); }
    if (!pl.obj.behind && pl.name !== 'center') drawObj();
    for (const i of front) { const p = pl.pts[i]; if (p) put(c, cuts[hs[i]], p[0], p[1], p[2]); }
    if (!pl.obj.behind && pl.name === 'center') drawObj();   // в схеме «по центру» вещь — впереди всех
    const clean = canvas(W, H); clean.getContext('2d').drawImage(out, 0, 0);
    P.decorate(c, ep, pl.mir ? 'left' : 'right'); say('Готово', 1);
    return { full: out, clean, info: { heroes: hs, emo, main: type || null, kind, scheme: pl.name + (pl.mir ? ' зеркально' : '') } }; };

  global.MKPoster = P;
})(typeof window !== 'undefined' ? window : globalThis);
