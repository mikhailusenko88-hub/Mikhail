// Никто ни в ком: node tools/multik/test/vnutri.js сценарий.txt [шаг=0.25] [--json]
// По состояниям сцены (без рисования, ~секунды на серию) ищет, где двое героев стоят друг в друге:
// расстояние по ширине сцены меньше 0,8 от полусуммы их ширин, оба на одной глубине, не идут и не обнимаются — дольше 1,5 с.
// Так было в серии 27 (движок 69c8530): Филя, отдав книгу, 25 секунд стоял внутри Рона. Код выхода 1, если нашлось.
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const args = process.argv.slice(2), file = args.find(a => !a.startsWith('--') && isNaN(+a)), step = +(args.find(a => !a.startsWith('--') && !isNaN(+a)) || .25), asJson = args.includes('--json');
if (!file) { console.error('нужен сценарий: node vnutri.js сценарий.txt [шаг]'); process.exit(2); }
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 640, height: 360 } }); p.on('pageerror', e => console.error('ERR', e.message));
  await p.goto('file://' + path.join(__dirname, 'frame.html') + '?noh6#nobarsik'); await p.waitForFunction(() => window.ready, null, { timeout: 900000 });
  const src = fs.readFileSync(file, 'utf8');
  const info = file.endsWith('.json') ? await p.evaluate(e => setup(e), JSON.parse(src)) : await p.evaluate(t => setupText(t), src);
  const out = await p.evaluate(([st, K, MIN]) => {
    const name = id => { const c = TL.lib.characters[id]; return (c && c.spec && c.spec.name) || id; }, open = {}, res = [];
    const close = (key, t) => { const o = open[key]; delete open[key]; if (o && t - o.t0 >= MIN) res.push({ sc: o.sc, t0: +o.t0.toFixed(2), t1: +t.toFixed(2), a: o.a, b: o.b, k: +o.k.toFixed(2) }); };
    for (const seg of TL.segs) { if (seg.kind !== 'scene' || !seg.C) continue;
      for (let t = 0; t <= seg.t1 - seg.t0; t += st) { const S = MK._sceneState(TL, seg, t, seg.t0 + t), ids = Object.keys(S).filter(i => S[i].vis && TL.lib.characters[i]), now = new Set();
        for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) { const A = S[ids[i]], B = S[ids[j]];
          if ((A.walk && A.walk.on) || (B.walk && B.walk.on) || (A.act && A.act.n === 'hug') || (B.act && B.act.n === 'hug')) continue;
          if (A.x < -.02 || A.x > 1.02 || B.x < -.02 || B.x > 1.02 || Math.abs((A.z || 0) - (B.z || 0)) > .3) continue;
          const w = (((seg.C[ids[i]] || {}).w || .1) + ((seg.C[ids[j]] || {}).w || .1)) / 2, k = Math.abs(A.x - B.x) / w; if (k >= K) continue;
          const key = seg.idx + '|' + ids[i] + '|' + ids[j]; now.add(key); if (!open[key]) open[key] = { sc: seg.idx, t0: seg.t0 + t, a: name(ids[i]), b: name(ids[j]), k }; else open[key].k = Math.min(open[key].k, k); }
        for (const key in open) if (!now.has(key)) close(key, seg.t0 + t); }
      for (const key in open) close(key, seg.t1); }
    return res; }, [step, .8, 1.5]);
  await b.close();
  const mmss = t => Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');
  if (asJson) console.log(JSON.stringify({ dur: info.dur, vnutri: out }));
  else { console.log('длина ' + (info.dur || 0).toFixed(1) + ' с; мест, где герой стоит в герое: ' + out.length); for (const r of out) console.log('  сцена ' + r.sc + '  ' + mmss(r.t0) + '–' + mmss(r.t1) + ' (' + r.t0 + '–' + r.t1 + ' с)  ' + r.a + ' и ' + r.b + '  расстояние ' + r.k + ' от полусуммы ширин'); }
  process.exit(out.length ? 1 : 0);
})();
