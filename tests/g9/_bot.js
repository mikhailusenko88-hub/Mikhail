// Общий водитель для проверок «Грязи». Два стиля: аккуратный (привод, блокировка и пониженная — только где нужны; знает камни, уступы, глину и осыпь)
// и «всё включено, газ в пол». Возвращает исход, время, груз, наименьший остаток топлива и время на лебёдке.
module.exports = function drive(S, waste, tmax = 600) {
  const L = S.L, b = S.cfg.b, tail = S.cfg.hb + 60 + (S.cfg.tr ? S.cfg.tr.len + 60 : 0); let t = 0, back = 0, hx = 0, hangs = 0, keep = false, minF = 1e9, wt = 0, ty = '', d = 0, up = false, retry = 0, rx = 0, tries = 0, px = -1e9, pt = 0;
  while (t < tmax && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + tail), wz = S.waterAt(x + 60), cr = L.signs.find((q) => q.kind === 'crest' && q.x > x - 500 && q.x < x + 700), rg = (L.rough || []).find((q) => x > q.x0 - 220 && x < q.x1 + tail);
    ty = z ? z.t : ''; d = z && ty === 'mud' ? z.d : 0; up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30; const slick = ty === 'clay' || ty === 'scree' || !!(z && z.inc);
    let inp = waste ? { gas: true, awd: !!b.awd, lock: !!b.lock, low: !!b.low && (up || !!z || !!rg), winch: !!S.rope || !!S.target }
      : { gas: true, awd: b.awd && (!!z || up || !!wz || !!cr || !!rg || S.stuckT > 0.4), lock: b.lock && (d >= 46 || ty === 'peat' || slick || !!rg || S.stuckT > 1), low: b.low && !cr && (d >= 56 || ty === 'peat' || up || keep || (!!rg && S.stuckT > 0.8) || !!(z && z.inc) || !!(wz && wz.depth > 55)), winch: (d >= 72 || ty === 'peat' || (slick && S.stuckT > 2.5)) && (!!S.rope || (S.stuckT > 1.5 && !!S.target)) };
    if (!z) keep = false; else if (ty !== 'sand' && ty !== 'scree' && S.stuckT > 1.1) keep = true;
    if (!waste) { // аккуратный водитель: под гору и перед камнями не гонит; встал на подъёме или осыпи — сдаёт назад и берёт с разгона, уже со всем включённым (как советует сама игра)
      const down = S.groundAt(x + 160) > S.groundAt(x - 40) + 30, near = (L.rough || []).find((q) => x > q.x0 - 420 && x < q.x1 + tail), v = S.truck.vx, lim = near ? (S.kindFragile ? 300 : 400) : down ? 420 : 1e9;
      if (v > lim * 1.25) { inp.gas = false; inp.brake = true; } else if (v > lim) inp.gas = false;
      if (x > px + 60) { px = x; pt = t; } const idle = t - pt > 4 && !S.rope; if (idle) pt = t; // качается на месте между камнями: скорость есть, хода нет — тоже повод сдать назад
      if (!retry && !back && !S.hung && ((S.stuckT > 2.2 && (up || slick || !!rg)) || idle) && tries < 6 && !S.rope) { retry = 1; rx = x; tries++; }
      if (retry === 1) { inp = { brake: true, awd: !!b.awd, lock: !!b.lock }; if (x < rx - 420 || S.stuckT > 4) retry = 2; }
      else if (retry === 2) { inp = { gas: true, awd: !!b.awd, lock: !!b.lock, low: !!b.low && tries > 1, winch: !!S.rope || (tries > 2 && !!S.target) }; if (x > rx + 300 || S.stuckT > 2.2) retry = 0; }
    }
    if (S.hung && S.stuckT > 1 && !back && S.truck.a <= 0.06) { back = 1; hx = x; hangs++; }
    if (back === 1) { inp = { brake: true, awd: !!b.awd }; if (x < hx - Math.min(900, 300 * hangs)) back = 2; } else if (back === 2) { inp = { gas: true, awd: !!b.awd, lock: !!b.lock && !!rg, low: !!b.low && !!rg }; if (x > hx + 500 || (S.hung && S.stuckT > 1 && S.truck.a <= 0.06)) back = 0; }
    S.step(inp); t += 1 / 120; S.events.length = 0; minF = Math.min(minF, S.fuel); if (S.rope) wt += 1 / 120; if (S.stuckT > 10 || hangs > 4) break; }
  const m = Math.round(S.truck.x / 54), where = S.hung ? 'брюхо' : rg0(L, S.truck.x) || (ty ? (ty === 'mud' ? 'грязь' + d : ty) : up ? 'подъём' : '');
  const why = S.state === 'win' ? '' : S.state === 'dead' ? '☠' + S.why + '@' + m + 'м' : 'встал@' + m + 'м' + (where ? '(' + where + ')' : '');
  return { ok: S.state === 'win', why, t: Math.round(t), cargo: S.cargo, of: S.cargo0, fuel: Math.round(100 * minF / S.cfg.tank), winch: Math.round(wt) };
};
function rg0(L, x) { const q = (L.rough || []).find((r) => x > r.x0 - 150 && x < r.x1 + 250); return q ? (q.t === 'rocks' ? 'камни' : 'уступ') : ''; }
