#!/usr/bin/env python3
"""Проба «образец → свой голос»: лучшие тембр (sluh_opt.py) и манера (sluh_man.py) сводятся вместе и проверяются на фразах,
которых подбор не видел (иначе можно «выучить» восемь фраз и не попасть в девятую).

  python svoy_proba.py <образец>   → cast10/proba_<образец>.json / .mp4 / .mp3 / _t0..2.flac / _w0..2.flac
  python svoy_proba.py merge       → cast10/svoy_voices.json (для onnx_svoy.py) и голоса для полного слуха в cast10/sluh_add_svoy.json
"""
import glob, json, os, subprocess, sys, traceback
try:
    import numpy as np
except ImportError:                 # merge работает и без numpy
    np = None

OUT = "cast10"
HELD = (1, 3, 4, 7, 8, 10, 12, 13, 15, 16)          # фразы phrases24 вне подбора (подбор шёл на 0, 2, 5, 6, 9, 11, 14, 17)
NPAIR = 6
NAME = {"n4": ("№4", "svoy_golos", "kbd_eduard"), "xenia": ("xenia — основа Барсика", "svoy_barsik", "bak_aigul"),
        "kseniya": ("kseniya — основа Рона", "svoy_ron", "bak_alfia"), "pik": ("голос Apple — Пик (только мерка)", "svoy_pik", "bak_ramilia")}
log = lambda *a: print(*a, flush=True)


def level(x):
    x = np.asarray(x, dtype=np.float32)
    y = x * (0.08 / float(np.sqrt((x ** 2).mean() + 1e-12)))
    m = float(np.abs(y).max())
    return y / m * 0.97 if m > 0.97 else y


BANDS = ((80, 300), (300, 1000), (1000, 3000), (3000, 6000), (6000, 10000), (10000, 16000))


def bands(W, T, sr=48000):
    """Насколько долгий спектр W отличается от образца T по полосам, дБ (уровень 200–4000 Гц уравнен)."""
    import sluh2
    fq, a = sluh2.power_spec(W, sr); _, b = sluh2.power_spec(T, sr)
    lv = lambda p, lo, hi: 10 * np.log10(p[(fq >= lo) & (fq < hi)].mean() + 1e-20)
    d0 = lv(a, 200, 4000) - lv(b, 200, 4000)
    return {f"{lo}-{hi}": round(float(lv(a, lo, hi) - lv(b, lo, hi) - d0), 1) for lo, hi in BANDS}


def eq_design(W, T, sr=48000, lim=9.0, f0=0.0, dead=1.5):
    import sluh2
    fq, ps = sluh2.power_spec(W, sr); _, pt_ = sluh2.power_spec(T, sr)
    g = 10 * np.log10((pt_ + 1e-20) / (ps + 1e-20))
    cen = np.geomspace(80, 16000, 48)
    box = lambda c: (fq >= c / 2 ** (1 / 6)) & (fq <= c * 2 ** (1 / 6))
    gs = np.array([float(np.mean(g[box(c)])) if box(c).any() else float(np.interp(c, fq, g)) for c in cen])      # на низах полоса у́же шага спектра
    gs = np.clip(gs - np.mean(gs[(cen > 200) & (cen < 4000)]), -lim, lim)
    gs = np.sign(gs) * np.maximum(0.0, np.abs(gs) - dead)     # мелкие расхождения (до dead дБ) не трогаем: правим только то, что слышно
    gs[cen < 0.7 * f0] = 0.0                        # ниже основного тона голоса нет — там только гул, его не поднимаем
    return cen, gs


def eq_apply(x, cen, gs, sr=48000):
    from scipy import signal
    freqs = np.concatenate([[0.0], cen, [sr / 2]]); gains = np.concatenate([[gs[0]], gs, [min(float(gs[-1]), 3.0)]])
    h = signal.firwin2(2049, freqs, 10 ** (gains / 20), fs=sr)
    return signal.fftconvolve(np.asarray(x, dtype=np.float64), h, mode="same").astype(np.float32)


def main(target, pin=False):
    import svoy_omo, svoy2, gen as g, sluh_opt, sluh_man, sluh2, svoy_lib as SL, svoy_bars, svoy_kot3 as K3
    for d in (OUT, "tmp", "models"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    L = sluh_opt.Lab(target)
    net = L.net
    keys = {r: k for k, (r, _) in net.tabs.items()}
    ph = sluh2.phrases24()
    held = [ph[i] for i in HELD if i < len(ph)]
    hero = sluh_man.HERO.get(target)
    if hero and os.path.exists("hero_lines.json"):          # герою проверка — на его репликах из мультика (семь проверочных, в подбор не входили)
        tst = json.load(open("hero_lines.json", encoding="utf-8")).get(hero + "@test", [])
        held = (tst + held)[:len(held)] if len(tst) >= 6 else held
    ru = svoy2.Net(svoy2.RU)
    if target == "n4":
        ru.put(ru.build(svoy_bars.W4)); spk = svoy2.SLOT[svoy2.RU]
    else:
        spk = target
    TW = []
    import tgt_ref
    for t in held:
        r = tgt_ref.rec(target, t)
        a = r if r is not None else ru.m.apply_tts(ssml_text=K3.text_for({"model": "ru", "pitch": "medium", "rate": "medium"}, t), speaker=spk, sample_rate=48000,
                                                    put_accent=True, put_yo=True).numpy()
        TW.append(np.asarray(a).copy())
    del ru

    def emb_all(W):
        E = {k: [] for k in sluh_opt.REF}
        for a in W:
            e = sluh2.embeds(L.to16(a))
            for k in E:
                E[k].append(e[k])
        return {k: L.norm(np.mean(v, 0)) for k, v in E.items()}

    TE = emb_all(TW)
    TC = [sluh_man.contour(w) for w in TW]
    f0t = float(np.median([c["f0"] for c in TC if c]))
    log("образец", target, "фраз", len(held), "высота", round(f0t, 1), "длины", [round(c["dur"], 2) for c in TC if c])

    wave = lambda a: a.numpy().copy() if hasattr(a, "numpy") else np.asarray(a)

    def tune_pitch(spe, ex, rate):
        """Средняя высота — к образцу. При SSML-высоте не medium модель сдвигает тон на (k − 1)·coef, значит coef — плавная ручка высоты."""
        if L.pitch == "medium":
            return ex, None
        ex = dict(ex or base_ex)

        def f0_at(c):
            e2 = dict(ex); e2["coef"] = float(c)
            fs = [sluh_man.contour(wave(L.say(spe, t, e2, rate))) for t in held[:5]]
            return float(np.median([c_["f0"] for c_ in fs if c_]))
        c1 = float(ex["coef"]); f1 = f0_at(c1)
        c2 = c1 * 1.3; f2 = f0_at(c2)
        tr = [(round(c1, 3), round(f1, 1)), (round(c2, 3), round(f2, 1))]
        for _ in range(2):
            if abs(f2 - f1) < 0.2 or abs(12 * np.log2(f2 / f0t)) < 0.15:
                break
            c3 = float(np.clip(c2 + (f0t - f2) * (c2 - c1) / (f2 - f1), 1.0, 14.0))
            c1, f1, c2 = c2, f2, c3; f2 = f0_at(c2)
            tr.append((round(c2, 3), round(f2, 1)))
        best = min(tr, key=lambda x: abs(np.log(x[1] / f0t)))
        ex["coef"] = float(best[0])
        return ex, tr

    def coef_true(spe, ex, rate):
        """Настоящее «средняя высота / разброс» выращенного голоса. Модель сдвигает тон на (k − 1)·coef места, куда вписан голос (в torch своё
        число туда не записать — список копируется), значит по высоте при k = 0,85 и 1,15 видно, каким coef должен быть, чтобы тон
        менялся ровно в k раз. Нужен движку мультика: там высота (P) и живость (R) считаются через это число."""
        c_slot = net.rows[svoy2.SLOT[svoy2.CIS]]["coef"]
        keep_p, f = L.pitch, {}
        try:
            for pit in ("medium", "low", "high"):
                L.pitch = pit; L.texts.clear()
                cs = [sluh_man.contour(wave(L.say(spe, t, ex, rate))) for t in held[:6]]
                f[pit] = float(np.mean([c_["f0"] for c_ in cs if c_]))
        finally:
            L.pitch = keep_p; L.texts.clear()
        est = [f["medium"] * (k - 1) * c_slot / (f[pit] - f["medium"]) for pit, k in (("low", 0.85), ("high", 1.15)) if abs(f[pit] - f["medium"]) > 0.5]
        return (round(float(np.mean(est)), 3) if est else None), {"slot": c_slot, **{k_: round(v, 1) for k_, v in f.items()}, "est": [round(float(e), 2) for e in est]}

    def measure(spe, ex, rate):
        return measure_waves([wave(L.say(spe, t, ex, rate)) for t in held])

    def measure_waves(W):
        E = emb_all(W)
        sims = {k: float(E[k] @ TE[k]) for k in E}
        pos = {k: (sims[k] - o) / (s - o) for k, (s, o) in sluh_opt.REF.items()}
        close = 0.5 * pos["ecapa"] + 0.25 * pos["wavlm"] + 0.25 * pos["resem"]
        C = [sluh_man.contour(w) for w in W]
        parts = [sluh_man.cmp(c, t) for c, t in zip(C, TC)]
        agg = {k: round(float(np.mean([p[1][k] for p in parts if k in p[1]])), 3) for k in ("mel", "ritm", "dur", "razmah", "rms")}
        f0 = float(np.median([c["f0"] for c in C if c]))
        return W, {"close": round(close, 4), "sims": {k: round(v, 3) for k, v in sims.items()}, "man": round(float(np.mean([p[0] for p in parts])), 4), **agg,
                   "f0": round(f0, 1), "pt": round(12 * np.log2(f0 / f0t), 2)}

    def quality(W, js=(0, 2, 5)):
        mt, ut = [], []
        for j in js:
            p = f"tmp/pq_{j}.wav"; g.save_wav(W[j], p)
            try:
                mt.append(SL.heard_match(p, held[j])[1]); ut.append(SL.utmos(SL.load(p, 16000)))
            except Exception:
                traceback.print_exc()
        return {"match": round(float(np.mean(mt)), 3) if mt else None, "utmos": round(float(np.mean(ut)), 2) if ut else None}

    old = f"{OUT}/proba_{target}.json"
    if pin and os.path.exists(old):            # строки голоса уже выбраны — заново только звук, эквалайзер и ролик
        p0 = json.load(open(old, encoding="utf-8"))
        tq, mb, table, win = p0["target_quality"], p0["base"], p0["table"], {k: v for k, v in p0["win"].items() if k not in ("spe_row", "pp_row", "dp_row", "eq")}
        spe = np.array(p0["win"]["spe_row"], dtype=float); rate = p0["win"]["rate"]
        ex = {keys["pp"]: np.array(p0["win"]["pp_row"]), keys["dp"]: np.array(p0["win"]["dp_row"]), "coef": p0["win"]["coef"]}
        W, m = measure(spe, ex, rate)
        log("закреплённый голос:", win["spe_from"], win["man_from"], rate, "близость была", win["close"], "сейчас", m["close"])
        win.update(m)
    else:
        tq = quality(TW)
        base_spe = L.base_rows[L.spe_key].double().numpy()
        found = []
        for f in sorted(glob.glob(f"{OUT}/opt_{target}_*.json")):
            pr = json.load(open(f, encoding="utf-8"))
            found.append((os.path.basename(f)[:-5], np.array(pr["win"]["spe"], dtype=float), pr["win"]["score"]))
        found.sort(key=lambda x: -x[2])
        late = [f for f in found if f[0][-1] in "bcd"]             # круги 2–4 (с третьего в оценке ещё и спектр — оценки кругов между собой не сравнивать)
        last = [f for f in late if f[0][-1] == "d"]
        found = (last + [f for f in late if f[0][-1] != "d"][:2]) if late else found[:3]
        mans = [("основа", None, "medium")]
        for f in sorted(glob.glob(f"{OUT}/man_{target}_*.json")):
            pr = json.load(open(f, encoding="utf-8"))
            k, w = pr["keys"], pr["win"]
            mans.append((os.path.basename(f)[:-5], {k["pp"]: np.array(w["pp"]), k["dp"]: np.array(w["dp"]), "coef": float(w["coef"])}, pr["rate"]))
        log("тембров", [(n, round(s, 3)) for n, _, s in found], "манер", [m[0] for m in mans])
        base_ex = {keys["pp"]: L.base_rows[keys["pp"]].double().numpy(), keys["dp"]: L.base_rows[keys["dp"]].double().numpy(), "coef": L.base_rows.get("coef")}
        Wb, mb = measure(base_spe, None, "medium")
        mb.update(quality(Wb))
        log("основа", mb)
        table = [{"spe_from": "основа", "man_from": "основа", "rate": "medium", **mb}]
        keep = {}
        for sn, spe, _ in found:
            for mn, ex, rate in mans:
                try:
                    ex, tr = tune_pitch(spe, ex, rate)
                    W, m = measure(spe, ex, rate)
                except Exception:
                    traceback.print_exc(); continue
                m.update(quality(W, (0, 1, 2, 3, 4, 5)))
                if tr:
                    m["coef_path"] = tr
                table.append({"spe_from": sn, "man_from": mn, "rate": rate, **m})
                keep[(sn, mn)] = (W, spe, ex, rate)
                log(sn, mn, m)
        rows = [r for r in table if r["spe_from"] != "основа"]
        ubest = max((r["utmos"] or 0) for r in rows); mbest = max((r["match"] or 0) for r in rows)
        for r in rows:        # близость голоса + манера − высота мимо − потеря естественности и разборчивости против лучшего из кандидатов
            r["J"] = round(r["close"] + 0.5 * r["man"] - 0.03 * max(0.0, abs(r["pt"]) - 0.5) - 0.3 * max(0.0, ubest - (r["utmos"] or 0) - 0.1)
                           - 0.5 * max(0.0, mbest - (r["match"] or 0) - 0.03), 4)
        cand = sorted(rows, key=lambda r: -r["J"])
        win = cand[0]
        W, spe, ex, rate = keep[(win["spe_from"], win["man_from"])]
        ex = ex or base_ex
    # эквалайзер под долгий спектр образца: считается на фразах подбора, проверяется на отложенных
    Wtr = [wave(L.say(spe, t, ex, rate)) for t in L.ph]
    cen, gs = eq_design(Wtr, L.tw, f0=f0t)
    We = [eq_apply(w, cen, gs) for w in W]
    _, me = measure_waves(We)
    eq = {"hz": [round(float(c), 1) for c in cen], "db": [round(float(v), 2) for v in gs], "before": bands(W, TW), "after": bands(We, TW),
          "close_before": win["close"], "close_after": me["close"], "sims_after": me["sims"], "used": bool(me["close"] >= win["close"] - 0.03)}
    log("эквалайзер", {int(c): round(float(v), 1) for c, v in zip(cen[::4], gs[::4])}, "полосы до", eq["before"], "после", eq["after"], "близость", win["close"], "→", me["close"])
    if eq["used"]:
        W = We
    try:
        ct, ctinfo = coef_true(spe, ex, rate)
    except Exception:
        traceback.print_exc(); ct, ctinfo = None, None
    log("coef настоящий:", ct, ctinfo)
    title, name, slot = NAME[target]
    out = {"target": target, "title": title, "name": name, "slot": slot, "held": held, "f0_target": round(f0t, 1), "target_quality": tq, "base": mb, "table": table,
           "win": {**{k: v for k, v in win.items()}, "pitch": L.pitch, "base_voice": sluh_opt.BASE[target][0], "spe_row": [round(float(v), 6) for v in spe],
                   "pp_row": [round(float(v), 6) for v in ex[keys["pp"]]], "dp_row": [round(float(v), 6) for v in ex[keys["dp"]]],
                   "coef": float(ex["coef"]) if ex.get("coef") is not None else None, "coef_true": ct, "coef_info": ctinfo, "eq": eq}}
    json.dump(out, open(f"{OUT}/proba_{target}.json", "w", encoding="utf-8"), ensure_ascii=False)
    # звук: пары «образец → свой голос»
    sr = 48000
    sil = lambda s: np.zeros(int(sr * s), dtype=np.float32)
    track, marks, t0 = [sil(0.5)], [], 0.5
    for j in range(min(NPAIR, len(held))):
        a, b = level(TW[j]), level(W[j])
        marks.append((j, "t", t0, t0 + len(a) / sr)); track += [a, sil(0.45)]; t0 += len(a) / sr + 0.45
        marks.append((j, "w", t0, t0 + len(b) / sr)); track += [b, sil(0.9)]; t0 += len(b) / sr + 0.9
        if j < 3:
            for tag, x in (("t", a), ("w", b)):
                g.save_wav(x, f"tmp/pf_{tag}{j}.wav")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"tmp/pf_{tag}{j}.wav", "-ar", "44100", "-ac", "1", f"{OUT}/proba_{target}_{tag}{j}.flac"], check=True)
    x = np.concatenate(track)
    g.save_wav(x, "tmp/proba.wav")
    out["marks"] = [[j, tag, round(a, 3), round(b, 3)] for j, tag, a, b in marks]
    json.dump(out, open(f"{OUT}/proba_{target}.json", "w", encoding="utf-8"), ensure_ascii=False)
    total = len(x) / sr
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    lab = {"t": f"ОБРАЗЕЦ: {title}", "w": "СВОЙ ГОЛОС (свободная модель)"}
    col = {"t": "0xbbbbbb", "w": "0x7CFC9A"}
    vf = []
    for j, tag, a, b in marks:
        for nm, text, size, y, c in ((f"l{tag}", lab[tag], 46 if len(lab[tag]) < 26 else 36, "h/2-60", col[tag]), (f"n{j}", f"фраза {j + 1} из {min(NPAIR, len(held))}", 30, "h/2+30", "0x8899aa")):
            p = f"tmp/pt_{nm}.txt"
            open(p, "w", encoding="utf-8").write(text)
            vf.append(f"drawtext=fontfile={font}:textfile={p}:fontsize={size}:fontcolor={c}:x=(w-text_w)/2:y={y}:enable='between(t,{a:.3f},{b:.3f})'")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "color=c=0x1e2230:s=1080x1080:r=25", "-i", "tmp/proba.wav", "-vf", ",".join(vf),
                    "-t", f"{total:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
                    "-movflags", "+faststart", f"{OUT}/proba_{target}.mp4"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "tmp/proba.wav", "-c:a", "libmp3lame", "-q:a", "3", f"{OUT}/proba_{target}.mp3"], check=True)
    log("готово", target, "основа", mb["close"], "→", win["close"], "манера", mb["man"], "→", win["man"], win["spe_from"], win["man_from"], f"{total:.1f} с")


def merge():
    V, add = {}, []
    for f in sorted(glob.glob(f"{OUT}/proba_*.json")):
        p = json.load(open(f, encoding="utf-8")); w = p["win"]
        V[p["name"]] = {"slot": p["slot"], "spe": w["spe_row"], "pp": w["pp_row"], "dp": w["dp_row"], "coef": w.get("coef_true") or w["coef"], "rate": w["rate"], "pitch": w["pitch"],
                        "eq": {"hz": w["eq"]["hz"], "db": w["eq"]["db"], "used": w["eq"]["used"]} if w.get("eq") else None,
                        "note": f"под {p['title']}: тембр {w['spe_from']}, манера {w['man_from']}; близость {w['close']} (основа {p['base']['close']})"}
        mix = {"w": "g03" if w["base_voice"] == "g03" else {r: {w["base_voice"]: 1.0} for r in ("dp", "pp", "spe")}, "spe_row": w["spe_row"], "pp_row": w["pp_row"],
               "dp_row": w["dp_row"], "coef": w["coef"], "pitch": w["pitch"], "rate": w["rate"]}
        if p["target"] == "n4":
            add.append({"name": "свой:№4", "group": "№4", "target": "n4@syn", "mix": mix, "kind": "mix", "note": "выращенный тембр и манера под №4"})
        else:
            hero, F = {"xenia": ("Барсик", 1.12), "kseniya": ("Рон", 1.08), "pik": ("Пик", 1.25)}[p["target"]]
            if p["target"] != "pik":           # у Пика нет образца «без движка» в слухе (голос Apple делает только Мак)
                add.append({"name": f"свой:{p['target']}", "group": p["target"], "target": f"{p['target']}@syn", "mix": mix, "kind": "mix", "note": f"выращенный голос под {p['target']} (без движка)"})
            for Fk in (F, round(F - 0.04, 2), round(F + 0.04, 2)):
                add.append({"name": f"свой:{hero}:{Fk}", "group": hero, "target": f"{hero}@g24", "mix": mix, "F": Fk, "auto": True, "eq": False, "kind": "emu",
                            "note": f"выращенный голос + подделка движка, форманты ×{Fk}"})
    json.dump({"voices": V}, open(f"{OUT}/svoy_voices.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"voices": add}, open(f"{OUT}/sluh_add_svoy.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)     # в sluh_add.json — копировать руками перед кругом слуха
    log("голоса:", list(V), "для слуха:", [a["name"] for a in add])


if __name__ == "__main__":
    merge() if sys.argv[1] == "merge" else main(sys.argv[1], pin=len(sys.argv) > 2 and sys.argv[2] == "pin")
