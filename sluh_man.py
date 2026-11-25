#!/usr/bin/env python3
"""Манера под образец — тем же способом, что тембр (sluh_opt.py): строки мелодии (pp) и ритма (dp) свободной модели и размах
мелодии (coef) растим эволюцией, а мерка — сама речь образца на тех же фразах.

Что сравнивается на каждой фразе (без выравнивания по звукам — время фразы приведено к 0…1):
  мелодия  — совпадение хода высоты (корреляция) и размах (отношение разбросов);
  ритм     — совпадение хода громкости (где слоги и паузы);
  темп     — длина фразы.
В sluh2.py видно, что два РАЗНЫХ диктора на одной фразе совпадают по мелодии на 0,77 — выше этого уже манера, а не текст.

  python sluh_man.py <образец> <зерно> <темп SSML: medium|fast> [поколений]
  → cast10/man_<образец>_<зерно>_<темп>.json (+ .mp3: три фразы образцом, потом находкой)
Тембр берётся из лучшей находки cast10/opt_<образец>_*.json.
"""
import glob, json, os, subprocess, sys, time, traceback
import numpy as np

OUT = "cast10"
log = lambda *a: print(*a, flush=True)
NPCM = 14
NG = 80


def contour(x48, sr=48000):
    """Фраза → ход высоты (пт от своей медианы) и громкости (дБ) на сетке 0…1, длина речи (с), медиана высоты (Гц)."""
    import parselmouth
    x = np.asarray(x48, dtype=np.float64)
    hop = int(sr * 0.01); n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    idx = np.where(e > e.max() * 10 ** (-38 / 20))[0]
    a, b = max(0, idx[0] - 2), min(n, idx[-1] + 3)
    x = x[a * hop:b * hop]; e = e[a:b]
    dur = len(x) / sr
    snd = parselmouth.Sound(x, sr)
    p0 = snd.to_pitch_ac(time_step=0.01, pitch_floor=50, pitch_ceiling=700).selected_array["frequency"]
    med = float(np.median(p0[p0 > 0])) if (p0 > 0).sum() > 5 else 0.0
    if med <= 0:
        return None
    pit = snd.to_pitch_ac(time_step=0.01, pitch_floor=max(40.0, med / 1.9), pitch_ceiling=med * 2.4)
    t, f = pit.xs(), pit.selected_array["frequency"]
    v = f > 0
    if v.sum() < 8:
        return None
    st = 12 * np.log2(f[v] / np.median(f[v]))
    g = np.linspace(0, 1, NG)
    fc = np.interp(g, t[v] / dur, st)
    env = 20 * np.log10(e / e.max() + 1e-4)
    k = np.ones(5) / 5
    env = np.convolve(env, k, mode="same")
    ec = np.interp(g, (np.arange(len(env)) + 0.5) / len(env), env)
    return {"f": fc, "e": ec, "dur": dur, "f0": float(np.median(f[v])), "sd": float(np.std(st)), "voiced": float(v.mean())}


HERO = {"xenia": "Барсик", "kseniya": "Рон"}


def pool_phrases(n, hero=None):
    """Фразы из запаса бота, которых нет ни в подборе тембра, ни в пробе (phrases24). Для героя — его реплики из серий 35–39
    (hero_lines.json; семь проверочных реплик пробы golosa в подбор не входят): в мультике много восклицаний и вопросов, а в запасе бота их нет."""
    import re, sluh2
    if hero:
        ls = json.load(open("hero_lines.json", encoding="utf-8"))[hero]
        return ls[::max(1, len(ls) // n)][:n] if len(ls) > n else ls
    used = set(sluh2.phrases24())
    B = json.load(open("bank/bank.json", encoding="utf-8"))
    ls = [l for s in B["scripts"] for l in s["lines"] if not re.search(r"\d", l) and 35 < len(l) < 95 and "—" not in l and ":" not in l and l not in used]
    ls = list(dict.fromkeys(ls))
    return ls[::max(1, len(ls) // n)][:n]


def cmp(c, t):
    """Близость манеры кандидата c к образцу t на одной фразе (чем больше, тем ближе) и её части."""
    if c is None or t is None:
        return -1.0, {}
    r = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-6 and b.std() > 1e-6 else 0.0
    rf, re_ = r(c["f"], t["f"]), r(c["e"], t["e"])
    ld = abs(np.log(c["dur"] / t["dur"])); ls = abs(np.log(max(c["sd"], 0.05) / max(t["sd"], 0.05)))
    rm = float(np.sqrt(np.mean((c["f"] - t["f"]) ** 2)))
    sc = 0.45 * rf + 0.25 * re_ - 0.6 * ld - 0.25 * ls - 0.03 * rm
    return sc, {"mel": rf, "ritm": re_, "dur": float(np.log(c["dur"] / t["dur"])), "razmah": float(np.log(max(c["sd"], 0.05) / max(t["sd"], 0.05))), "rms": rm}


def main(target, seed, rate, gens):
    import cma, svoy_omo, svoy2, gen as g, sluh_opt
    for d in (OUT, "tmp", "models"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    L = sluh_opt.Lab(target)
    torch, net = L.torch, L.net
    # тембр — лучшая находка (по близости к образцу)
    spe, src = L.base_rows[L.spe_key].double().numpy(), "основа"
    best_sc = -9
    for f in sorted(glob.glob(f"{OUT}/opt_{target}_*.json")):
        pr = json.load(open(f, encoding="utf-8"))
        if pr["win"].get("close", pr["win"]["score"]) > best_sc:
            best_sc, spe, src = pr["win"].get("close", pr["win"]["score"]), np.array(pr["win"]["spe"], dtype=float), os.path.basename(f)
    log("тембр:", src, best_sc)
    # фразы: восемь из подбора тембра + запас бота; последние десять — только для проверки (подбор их не видит)
    POOL = int(os.environ.get("POOL", "0"))
    PH, TWall = list(L.ph), list(L.tw)
    if POOL:
        import svoy_bars, svoy_kot3 as K3
        hero = HERO.get(target) if os.environ.get("HEROPOOL") == "1" else None
        extra_ph = pool_phrases(POOL + 10, hero)
        if hero:
            PH, TWall = [], []                 # герою — только его реплики
            log("фразы героя:", hero, len(extra_ph))
        ru = svoy2.Net(svoy2.RU)
        if target == "n4":
            ru.put(ru.build(svoy_bars.W4)); spk = svoy2.SLOT[svoy2.RU]
        else:
            spk = target
        for t in extra_ph:
            a = ru.m.apply_tts(ssml_text=K3.text_for({"model": "ru", "pitch": "medium", "rate": "medium"}, t), speaker=spk, sample_rate=48000, put_accent=True, put_yo=True)
            PH.append(t); TWall.append(a.numpy().copy())
        del ru
    NV = 10 if POOL else 0
    TRAIN = list(range(len(PH) - NV)); VAL = list(range(len(PH) - NV, len(PH))) or list(range(8))
    log("фраз для подбора", len(TRAIN), "для проверки", len(VAL))
    keys = {r: k for k, (r, _) in net.tabs.items()}
    names = [s for s in net.ids if s in net.rows and not s.startswith("ru_nash")]
    PC = {}
    for role in ("pp", "dp"):
        M = torch.stack([net.rows[s][keys[role]] for s in names]).double().numpy()
        mu = M.mean(0)
        U, sv, Vt = np.linalg.svd(M - mu, full_matrices=False)
        nr = np.linalg.norm(M, axis=1)
        PC[role] = {"mu": mu, "pc": Vt[:NPCM], "sd": sv[:NPCM] / np.sqrt(len(names) - 1), "lo": float(np.percentile(nr, 10)), "hi": float(np.percentile(nr, 90)), "M": M}
    coefs = [net.rows[s]["coef"] for s in names if net.rows[s].get("coef")]
    c0 = float(L.base_rows.get("coef") or np.median(coefs))
    log("coef дикторов:", round(float(np.min(coefs)), 2), "…", round(float(np.max(coefs)), 2), "основа", round(c0, 2))

    def zof(role, row):
        P = PC[role]
        return ((np.asarray(row, dtype=float) - P["mu"]) @ P["pc"].T) / P["sd"]

    def rowof(role, z):
        P = PC[role]
        r = P["mu"] + (np.asarray(z) * P["sd"]) @ P["pc"]
        n = np.linalg.norm(r)
        return r * (min(max(n, P["lo"]), P["hi"]) / (n + 1e-9))

    def extra(x):
        x = np.asarray(x)
        return {keys["pp"]: rowof("pp", x[:NPCM]), keys["dp"]: rowof("dp", x[NPCM:2 * NPCM]), "coef": float(np.clip(c0 * np.exp(x[2 * NPCM] * 0.25), 1.5, 12.0))}

    TC = [contour(w) for w in TWall]
    f0t = float(np.median([c["f0"] for c in TC if c]))
    log("образец: высота", round(f0t, 1), "длины", [round(c["dur"], 2) for c in TC[:8] if c], "размах", [round(c["sd"], 2) for c in TC[:8] if c])

    def score(ex, idx):
        S, parts, f0 = [], [], []
        for i in idx:
            a = L.say(spe, PH[i], ex, rate)
            c = contour(a.numpy() if hasattr(a, "numpy") else np.asarray(a))
            sc, pt = cmp(c, TC[i])
            S.append(sc); parts.append(pt)
            if c:
                f0.append(c["f0"])
        agg = {k: round(float(np.mean([p[k] for p in parts if k in p])), 3) for k in ("mel", "ritm", "dur", "razmah", "rms")} if any(parts) else {}
        pt = 12 * np.log2(float(np.median(f0)) / f0t) if f0 else 9.0
        agg["pt"] = round(float(pt), 2)
        return float(np.mean(S)) - 0.05 * max(0.0, abs(pt) - 0.3), agg       # средняя высота — как у образца (±0,3 полутона без штрафа)

    all8 = VAL                                    # полная оценка — на фразах проверки
    # старты: основа и манера каждого готового диктора
    cand = []
    probe = TRAIN[::max(1, len(TRAIN) // 4)][:4]
    for s in names:
        if not s.startswith("ru_"):
            continue
        ex = {keys["pp"]: net.rows[s][keys["pp"]].double().numpy(), keys["dp"]: net.rows[s][keys["dp"]].double().numpy(), "coef": float(net.rows[s].get("coef") or c0)}
        sc, agg = score(ex, probe)
        cand.append((sc, s, agg, ex))
    prev = f"{OUT}/man_{target}_{seed}_{rate}.json"
    if os.path.exists(prev):                       # прошлая находка — тоже старт
        try:
            pw = json.load(open(prev, encoding="utf-8"))["win"]
            ex = {keys["pp"]: np.array(pw["pp"]), keys["dp"]: np.array(pw["dp"]), "coef": float(pw["coef"])}
            sc, agg = score(ex, probe); cand.append((sc, "прошлая находка", agg, ex))
        except Exception:
            traceback.print_exc()
    cand.sort(key=lambda x: -x[0])
    log("манера готовых дикторов:", [(s, round(sc, 3), a.get("mel"), a.get("dur")) for sc, s, a, _ in cand[:8]])
    ex0 = {keys["pp"]: L.base_rows[keys["pp"]].double().numpy(), keys["dp"]: L.base_rows[keys["dp"]].double().numpy(), "coef": c0}
    sb, ab = score(ex0, all8)
    log("основа:", round(sb, 4), ab)
    best = (sb, ex0, ab, "основа")
    for sc, s, agg, ex in cand[:3]:
        s8, a8 = score(ex, all8)
        log("старт", s, round(s8, 4), a8)
        if s8 > best[0]:
            best = (s8, ex, a8, s)
    x0 = np.concatenate([zof("pp", best[1][keys["pp"]]), zof("dp", best[1][keys["dp"]]), [np.log(best[1]["coef"] / c0) / 0.25]])
    x0 = np.clip(x0, -3.4, 3.4)
    es = cma.CMAEvolutionStrategy(x0.tolist(), 0.3, {"popsize": 14, "seed": seed + 1, "bounds": [-3.5, 3.5], "verbose": -9})
    rnd = np.random.default_rng(seed)
    trail, t0, top = [], time.time(), [(best[0], best[1], best[2])]
    for gi in range(gens):
        idx = sorted(rnd.choice(TRAIN, size=min(6, len(TRAIN)), replace=False).tolist())
        X = es.ask()
        F = []
        for x in X:
            try:
                sc, _ = score(extra(x), idx)
            except Exception as e:
                log("ОШИБКА", repr(e)); sc = -2.0
            F.append(-sc)
        es.tell(X, F)
        if gi % 5 == 4 or gi == gens - 1:
            ex = extra(es.mean)
            sc, agg = score(ex, all8)
            top.append((sc, ex, agg))
            trail.append({"gen": gi + 1, "score": round(sc, 4), **agg, "coef": round(ex["coef"], 2), "min": round((time.time() - t0) / 60, 1)})
            log("поколение", gi + 1, trail[-1])
        if time.time() - t0 > 65 * 60:
            log("время вышло"); break
    top.sort(key=lambda x: -x[0])
    res = []
    import svoy_lib as SL
    for sc, ex, agg in top[:3]:
        mt, ut, E = [], [], {k: [] for k in sluh_opt.REF}
        QI = VAL[:3]
        TEq = {k: [] for k in sluh_opt.REF}
        for i in QI:
            p = f"tmp/q_{i}.wav"
            a = L.say(spe, PH[i], ex, rate); g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
            try:
                mt.append(SL.heard_match(p, PH[i])[1]); ut.append(SL.utmos(SL.load(p, 16000)))
                e = L.S.embeds(L.to16(a)); et = L.S.embeds(L.to16(TWall[i]))
                for k in E:
                    E[k].append(e[k]); TEq[k].append(et[k])
            except Exception:
                traceback.print_exc()
        sims = {k: round(float(L.norm(np.mean(v, 0)) @ L.norm(np.mean(TEq[k], 0))), 3) for k, v in E.items() if v}
        res.append({"score": round(sc, 4), **agg, "match": round(float(np.mean(mt)), 3) if mt else None, "utmos": round(float(np.mean(ut)), 2) if ut else None,
                    "sims": sims, "coef": ex["coef"], "pp": [round(float(v), 6) for v in ex[keys["pp"]]], "dp": [round(float(v), 6) for v in ex[keys["dp"]]]})
        log("итог", {k: v for k, v in res[-1].items() if k not in ("pp", "dp")})
    ok = [r for r in res if (r["match"] or 0) >= 0.85] or res
    win = ok[0]
    out = {"target": target, "seed": seed, "rate": rate, "spe_from": src, "spe": [round(float(v), 6) for v in spe], "base": {"score": round(sb, 4), **ab},
           "start": {"name": best[3], "score": round(best[0], 4), **best[2]}, "ready": [(s, round(sc, 4), a) for sc, s, a, _ in cand[:10]],
           "trail": trail, "best": res, "win": win, "keys": keys, "pitch": L.pitch}
    json.dump(out, open(f"{OUT}/man_{target}_{seed}_{rate}.json", "w", encoding="utf-8"), ensure_ascii=False)
    parts = []
    exw = {keys["pp"]: np.array(win["pp"]), keys["dp"]: np.array(win["dp"]), "coef": win["coef"]}
    for j, i in enumerate(VAL[:3]):
        p = f"tmp/t_{j}.wav"; g.save_wav(TWall[i], p); parts.append(p)
    for j, i in enumerate(VAL[:3]):
        p = f"tmp/w_{j}.wav"; a = L.say(spe, PH[i], exw, rate); g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p); parts.append(p)
    lst = "tmp/list.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "libmp3lame", "-q:a", "3",
                    f"{OUT}/man_{target}_{seed}_{rate}.mp3"], check=True)
    for j, p in enumerate(parts):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ar", "44100", "-ac", "1", f"{OUT}/man_{target}_{seed}_{rate}_{'t' if j < 3 else 'w'}{j % 3}.flac"], check=True)
    log("готово", target, seed, rate, "основа", round(sb, 4), "→", win["score"])


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 80)
