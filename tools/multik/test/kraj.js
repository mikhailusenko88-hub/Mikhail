// Край кадра режет героя: node tools/multik/test/kraj.js сценарий.txt [шаг=1] [--json] [--all]
// Для каждого плана (по умолчанию — средние; --all — все, кроме общего) каждые «шаг» секунд рисует кадр и по настоящим габаритам героев
// считает, какая доля героя по ширине видна в кадре. «Разрезан» — видно от 20% до 80% (половина героя у края); «краешек» — меньше 20%; больше 80% — не считается.
// Сводка: сколько секунд средних планов с разрезанным героем и список планов. Нужна для правки камеры (edgeFit) и для приёмки.
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const args = process.argv.slice(2), file = args.find(a => !a.startsWith('--') && isNaN(+a)), step = +(args.find(a => !a.startsWith('--') && !isNaN(+a)) || 1), asJson = args.includes('--json'), all = args.includes('--all');
if (!file) { console.error('нужен сценарий: node kraj.js сценарий.txt [шаг]'); process.exit(2); }
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 640, height: 360 } }); p.on('pageerror', e => console.error('ERR', e.message));
  await p.goto('file://' + path.join(__dirname, 'frame.html') + '?noh6#nobarsik'); await p.waitForFunction(() => window.ready, null, { timeout: 180000 });
  const src = fs.readFileSync(file, 'utf8');
  const info = file.endsWith('.json') ? await p.evaluate(e => setup(e), JSON.parse(src)) : await p.evaluate(t => setupText(t), src);
  await p.evaluate(() => { const c = document.getElementById('c'); c.width = 192; c.height = 108; });
  const out = await p.evaluate(([st, all]) => {
    const D = MK3D._dbg(), T3 = D.THREE, rc = MK3D.rigs(), box = new T3.Box3(), v = new T3.Vector3(), res = [];
    const name = id => { const c = TL.lib.characters[id]; return (c && c.spec && c.spec.name) || id; };
    for (const seg of TL.segs) { if (seg.kind !== 'scene' || !seg.cam) continue; const cs = seg.cam.filter(c => !c.shake);
      cs.forEach((c, j) => { if (!(all ? c.mode !== 'wide' : c.mode === 'medium')) return; const t0 = c.t + (c.cut ? .05 : .95), t1 = (j + 1 < cs.length ? cs[j + 1].t : seg.t1 - seg.t0) - .05; if (t1 <= t0) return;
        const shot = { sc: seg.idx, t0: +(seg.t0 + c.t).toFixed(1), t1: +(seg.t0 + t1).toFixed(1), mode: c.mode, on: name(c.on), cut: {}, sliver: {}, n: 0, bad: 0 };
        for (let t = t0; t <= t1; t += st) { frame(seg.t0 + t); D.cam.updateMatrixWorld(); shot.n++; let badNow = false;
          for (const k in rc) { const r = rc[k]; if (!r.root.visible || !r.root.parent) continue; box.setFromObject(r.root); if (box.isEmpty()) continue;
            let a = 9, bb = -9, front = false; const zc = (box.min.z + box.max.z) / 2; for (let i = 0; i < 4; i++) { v.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, zc).project(D.cam);   /* по средней глубине героя: ближние углы коробки дают лишнюю ширину */ if (v.z < 1) front = true; a = Math.min(a, v.x); bb = Math.max(bb, v.x); }
            if (!front || bb <= a) continue; const f = Math.max(0, Math.min(1, bb) - Math.max(-1, a)) / (bb - a), nm = (r.spec && r.spec.name) || k;
            if (f > .2 && f < .8) { if (shot.cut[nm] == null || Math.abs(f - .5) < Math.abs(shot.cut[nm] - .5)) shot.cut[nm] = +f.toFixed(2); badNow = true; } else if (f > .01 && f <= .2) shot.sliver[nm] = 1; }
          if (badNow) shot.bad++; }
        res.push(shot); }); }
    return res; }, [step, all]);
  await b.close();
  const mmss = t => Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');
  const bad = out.filter(s => s.bad), secs = out.reduce((a, s) => a + s.bad * step, 0), tot = out.reduce((a, s) => a + s.n * step, 0), sl = out.filter(s => !s.bad && Object.keys(s.sliver).length);
  if (asJson) console.log(JSON.stringify({ dur: info.dur, shots: out.length, bad: bad.length, badSec: secs, totSec: tot, list: out }));
  else { console.log('планов: ' + out.length + ' (' + tot.toFixed(0) + ' с); с разрезанным героем: ' + bad.length + ' (' + secs.toFixed(0) + ' с); только краешек у края: ' + sl.length);
    for (const s of bad) console.log('  сцена ' + s.sc + '  ' + mmss(s.t0) + '–' + mmss(s.t1) + ' (' + s.t0 + '–' + s.t1 + ')  ' + s.mode + ' ' + s.on + ':  разрезан ' + Object.keys(s.cut).map(n => n + ' (видно ' + Math.round(s.cut[n] * 100) + '%)').join(', ') + '  — ' + s.bad + ' из ' + s.n + ' кадров'); }
})();
