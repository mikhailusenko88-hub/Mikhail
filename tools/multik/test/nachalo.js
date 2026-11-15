// Начало серии (сборка 59): заставка не в начале, «холодный старт» первой сцены, главный предмет, проверка «Начало серии».
//   node tools/multik/test/nachalo.js [--ref=коммит] сценарий.txt …   (без сценариев — все *.txt из этой папки)
// 1) «как было» (Заставка: в начале, Начало серии: как было) — серия кадр в кадр как в движке ref (по умолчанию — HEAD~ от коммита сборки 58);
// 2) «новое» — на кадре 0 сцена с героями (не заставка, не пустой общий план), первая речь ≤ 1,5 с, заставка 3 с после первой сцены,
//    входы до первой реплики — уже на местах, входы позже — как раньше (идут), вещи в лапах на местах, «ищем клад» — клад заранее не появляется,
//    ошибок разбора 0, плашка подписки не на заставке.
const fs = require('fs'), path = require('path'), vm = require('vm'), cp = require('child_process');
const args = process.argv.slice(2), opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const ROOT = path.resolve(__dirname, '../../../Resources/Mebel'), FILES = ['multik-engine.js', 'multik-audio.js', 'multik-maker.js', 'multik-script.js'];
const ref = opt('ref') || '9e2d193e', refDir = fs.mkdtempSync('/tmp/nachalo-ref-');
for (const f of FILES) fs.writeFileSync(path.join(refDir, f), cp.execSync(`git show ${ref}:Resources/Mebel/${f}`, { cwd: ROOT, maxBuffer: 64 << 20 }));
function load(dir) { const ctx = { console, Math, Date, JSON, Object, Array, Set, Map, Float32Array, Int16Array, Uint8Array, Uint32Array, Int32Array, Float64Array, String, Number, RegExp, Error, isNaN, parseInt, parseFloat, Promise, setTimeout };
  ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx; vm.createContext(ctx); for (const f of FILES) vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), ctx, { filename: f }); return ctx; }
const A = load(refDir), B = load(ROOT);
const HEROES = 'ПЕРСОНАЖ: Барсик — рыжий полосатый котёнок с синим шарфом, голос мальчика\nПЕРСОНАЖ: Пик — маленький серый мышонок с красным бантиком, голос девочки\nПЕРСОНАЖ: Рон — маленький серый пёс с белым животом, белые лапки, с белой кепкой, голос мальчика\n';
const withHeroes = t => /ПЕРСОНАЖ:\s*Барсик/.test(t) ? t : t.replace(/^(СЕРИЯ[^\n]*\n)/m, '$1' + HEROES);   // герои из библиотеки телефона
const strip = tl => JSON.stringify({ dur: tl.dur, segs: tl.segs.map(s => ({ k: s.kind, t0: s.t0, t1: s.t1, cam: s.cam, C: s.C, props: s.props && s.props.map(p => ({ type: p.type, x: p.x0, ev: p.ev, big: p.big, vis0: p.vis0 })) })), speech: tl.speech, sfx: tl.sfx, music: tl.music, sub: tl.sub });
let bad = 0; const ok = (c, m) => { console.log((c ? '  ✔ ' : '  ✘ ') + m); if (!c) bad++; };
let files = args.filter(a => !a.startsWith('--')); if (!files.length) files = fs.readdirSync(__dirname).filter(f => f.endsWith('.txt')).map(f => path.join(__dirname, f));
for (const f of files) { const txt = withHeroes(fs.readFileSync(f, 'utf8')); console.log('▶', path.basename(f));
  const mk = (X, settings) => { const lib = { characters: {}, locations: {}, settings }; const r = X.MKScript.parse(txt, lib); for (const c of r.newChars) lib.characters[c.id] = { spec: c }; for (const l of r.newLocs) lib.locations[l.id] = { spec: l }; return { r, lib }; };
  const a = mk(A, {}), o = mk(B, { intro: 'start', opening: 'old' }), n = mk(B, {});
  ok(n.r.errors.length === 0 && n.r.errors.length === a.r.errors.length, `ошибок разбора ${n.r.errors.length} (в прежней версии ${a.r.errors.length})`);
  // движок: тот же разбор, «как было» — кадр в кадр как прежний движок
  for (let i = 0; i < o.r.episodes.length; i++) { const eo = o.r.episodes[i], ea2 = JSON.parse(JSON.stringify(eo)); ok(strip(A.MK.compile(ea2, o.lib, {})) === strip(B.MK.compile(eo, o.lib, {})), `серия ${eo.episode}: «как было» — кадр в кадр как прежний движок`); }
  // разбор: что изменилось в вещах сцен (ждём только луну/радугу и деревья из разговора — правка 15.11)
  for (let i = 0; i < a.r.episodes.length; i++) { const ea = a.r.episodes[i], eb = o.r.episodes[i]; const ty = sc => (sc.props || []).map(p => p.type + (p.hidden ? '?' : '')).sort().join(','), dif = [];
    ea.scenes.forEach((sc, j) => { const x = ty(sc), y = eb.scenes[j] ? ty(eb.scenes[j]) : '—'; if (x !== y) dif.push(`сцена ${j + 1}: ${x || '—'} → ${y || '—'}`); });
    const other = dif.filter(d => { const [, x, y] = d.match(/: (.*) → (.*)$/); const cl = z => z.split(',').filter(t => t && t !== '—' && !/^(moon|rainbow|tree)\??$/.test(t)).join(','); return cl(x) !== cl(y); });
    ok(!other.length && ea.scenes.length === eb.scenes.length, `серия ${ea.episode}: разбор тот же${dif.length ? ' (кроме луны/деревьев: ' + dif.join('; ') + ')' : ''}${other.length ? ' — ИЗМЕНИЛОСЬ: ' + other.join('; ') : ''}`); }
  for (const ep of n.r.episodes) { const tl = B.MK.compile(ep, n.lib, {}), s0 = tl.segs[0], sc0 = ep.scenes[0], nm = id => (n.lib.characters[id] || { spec: { name: id } }).spec.name;
    const st = id => { const cd = s0.C[id], cs = sc0.cast.find(c => c.who === id); const ev = cd.ev.slice().sort((p, q) => p.t - q.t); let vis = !cs.hidden, x = cs._x != null ? cs._x : cs.x; for (const e of ev) { if (e.t > .05) break; if (e.k === 'vis') vis = e.v; if (e.k === 'move') x = e.x1; } return { vis, x }; };
    ok(s0.kind === 'scene', `серия ${ep.episode}: кадр 0 — сцена, не заставка`);
    const iH = sc0.steps.findIndex(x => x.say && x.who && x.who !== 'Р'), early = sc0.steps.slice(0, iH < 0 ? sc0.steps.length : iH + 1).filter(x => x.do === 'enter' && x.who && s0.C[x.who]);
    const late = sc0.steps.slice(iH < 0 ? sc0.steps.length : iH + 1).filter(x => x.do === 'enter' && x.who && s0.C[x.who] && !early.some(e => e.who === x.who));
    ok(early.every(x => st(x.who).vis), `входы до первой реплики (${[...new Set(early.map(x => nm(x.who)))].join(', ') || '—'}) — уже на местах с кадра 0`);
    ok(late.every(x => s0.C[x.who].ev.some(e => e.k === 'move' && (e.x0 < 0 || e.x0 > 1))), `входы по сюжету позже (${[...new Set(late.map(x => nm(x.who)))].join(', ') || '—'}) — идут, как раньше`);
    const vis0 = Object.keys(s0.C).filter(id => st(id).vis), c0 = s0.cam.filter(c => c.t <= .01).pop();
    const c1 = s0.cam.find(c => c.mode !== 'wide'); ok(!vis0.length || c0.mode !== 'wide' || (c1 && c1.t <= 1.7), `первый план — ${c0.mode}${c0.mode === 'wide' && c1 ? ` до ${c1.t.toFixed(1)} с (луна/радуга в небе), потом ${c1.mode}` : ''}${vis0.length ? '' : ' (героев в начале нет)'}; общий план места — не дольше 1,5 с`);
    const sp = tl.speech[0], act0 = sc0.steps.slice(0, sc0.steps.findIndex(x => x.say || x.vocal) < 0 ? 0 : sc0.steps.findIndex(x => x.say || x.vocal)).some(x => (x.do && x.do !== 'enter') || x.sfx || (x.prop && x.state));
    ok(!sp || sp.t <= 1.5 || (act0 && sp.t <= 5), `первая речь на ${sp ? sp.t.toFixed(2) : '—'} с (≤ 1,5${act0 ? '; до неё действие — порядок не ломаем, ≤ 5' : ''})`);
    const T = tl.segs.find(x => x.kind === 'title'); ok(tl.intro.mode !== 'after' || (T && T.t0 >= 12 && T.t1 - T.t0 === 3 && T.t0 === tl.segs[1].t0), `заставка: ${tl.intro.mode}${T ? ` ${T.t0.toFixed(1)}–${T.t1.toFixed(1)} с` : ''}`);
    ok(!T || !tl.sub || tl.sub.marks.every(m => m + 7 <= T.t0 || m >= T.t1), 'плашка подписки не попадает на заставку');
    const held = s0.props.filter(p => p.h0); ok(held.every(p => st(p.h0).vis || !early.some(e => e.who === p.h0)), `вещи в лапах с начала: ${held.map(p => p.type + ' у ' + nm(p.h0)).join(', ') || '—'}`);
    const tz = s0.props.find(p => p.teaser), ma = s0.mainAt != null ? s0.mainAt - s0.t0 : null;
    ok(!tz || !(ep.absent || []).includes(tz.type), `главный предмет: ${ep.main || '—'}${ma != null ? ` — в кадре на ${ma.toFixed(1)} с${tz ? ' (мелькнёт)' : ''}` : ep.main ? ((ep.absent || []).includes(ep.main) ? ' — по сюжету появляется позже, заранее не показываю' : ' — в первые 10 с его нет') : ''}`);
    console.log('    проверка «Начало серии»:', B.MK.introCheck(ep, n.lib).map(w => w.k).join(', ') || 'всё хорошо'); } }
console.log(bad ? `✘ ошибок: ${bad}` : '✔ всё в порядке'); process.exit(bad ? 1 : 0);
