// План камер и кадры с длительностями реплик из настоящей сборки студии: node _tlaud.js сценарий.txt runs/<имя>/speech.json [--hq] [--out=папка] [--plan=секунд] t1 t2 …
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const a = process.argv.slice(2), file = a[0], sp = JSON.parse(fs.readFileSync(a[1], 'utf8')), hq = a.includes('--hq'), out = (a.find(x => x.startsWith('--out=')) || '--out=.').slice(6), plan = +((a.find(x => x.startsWith('--plan=')) || '--plan=0').slice(7)), times = a.slice(2).filter(x => !x.startsWith('--')).map(Number);
(async () => { const b = await chromium.launch({ timeout: 180000, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('file://' + path.join(__dirname, 'frame.html') + (process.env.H6 ? '?' + process.env.H6 : '') + (hq ? '#hq' : '')); await p.waitForFunction(() => window.ready, null, { timeout: 900000 });
  const info = await p.evaluate(([txt, S, T]) => { const r = MKScript.parse(txt, { characters: {}, locations: {} }), ep = r.episodes[0], lib = { characters: {}, locations: {}, settings: window.SETTINGS || {} };
    const v = MK.validate(ep, lib); for (const c of v.newChars) lib.characters[c.id] = { spec: c, code: c._code }; for (const l of v.newLocs) lib.locations[l.id] = { spec: l, code: l._code };
    const norm = s => (s || '').toLowerCase().replace(/[^а-яё]/g, ''), D = {}; for (const x of S.speech) if (!x.vocal) (D[norm(x.text)] = D[norm(x.text)] || []).push(x.dur);
    const audio = {}; let n = 0; for (const sc of ep.scenes) for (const st of sc.steps || []) { const tx = st.say || st.text; if (!tx || !st.who) continue; const l = MK.lineFor(ep, lib, st.who, tx, st, 0); const d = D[norm(tx)]; if (l && d && d.length) { audio[l.key] = { dur: d[0] }; n++; } }
    window.TL = MK.compile(ep, lib, audio); TL.style = '3d'; const name = id => { const c = TL.lib.characters[id]; return (c && c.spec && c.spec.name) || id; };
    const sg = TL.segs.filter(s => s.t0 < T).map(s => `[${s.t0.toFixed(1)}-${s.t1.toFixed(1)}] ${s.kind} ${(s.cam || []).filter(c => c.t < T).map(c => c.t.toFixed(1) + ':' + c.mode + (c.on ? '/' + name(c.on) : '') + (c.zoom ? '/z' + c.zoom : '') + (c.prop ? '/' + c.prop : '')).join(' ')}`);
    return { matched: n, dur: TL.dur, plan: sg.join('\n') }; }, [fs.readFileSync(file, 'utf8'), sp, plan || 30]);
  console.log('реплик с настоящей длиной:', info.matched, 'длина', info.dur.toFixed(1)); console.log(info.plan);
  for (const t of times) { await p.evaluate(t => { const c = document.getElementById('c'); c.width = 1280; c.height = 720; frame(t); }, t); await p.waitForTimeout(hq ? 1500 : 200);
    const f = path.join(out, `a_${t}.png`); await (await p.$('#c')).screenshot({ path: f }); console.log(f); }
  await b.close(); })();
