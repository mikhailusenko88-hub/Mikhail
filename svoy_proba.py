#!/usr/bin/env python3
"""Проба «образец → свой голос»: лучшие тембр (sluh_opt.py) и манера (sluh_man.py) сводятся вместе и проверяются на фразах,
которых подбор не видел (иначе можно «выучить» восемь фраз и не попасть в девятую).

  python svoy_proba.py <образец>   → cast10/proba_<образец>.json / .mp4 / .mp3 / _t0..2.flac / _w0..2.flac
  python svoy_proba.py merge       → cast10/svoy_voices.json (для onnx_svoy.py) и голоса для полного слуха в sluh_add.json
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
        "kseniya": ("kseniya — основа Рона", "svoy_ron", "bak_alfia")}
log = lambda *a: print(*a, flush=True)


def level(x):
    x = np.asarray(x, dtype=np.float32)
    y = x * (0.08 / float(np.sqrt((x ** 2).mean() + 1e-12)))
    m = float(np.abs(y).max())
    return y / m * 0.97 if m > 0.97 else y


def main(target):
    import svoy_omo, svoy2, gen as g, sluh_opt, sluh_man, sluh2, svoy_lib as SL, svoy_bars, svoy_kot3 as K3
    for d in (OUT, "tmp", "models"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    L = sluh_opt.Lab(target)
    net = L.net
    keys = {r: k for k, (r, _) in net.tabs.items()}
    ph = sluh2.phrases24()
    held = [ph[i] for i in HELD if i < len(ph)]
    ru = svoy2.Net(svoy2.RU)
    if target == "n4":
        ru.put(ru.build(svoy_bars.W4)); spk = svoy2.SLOT[svoy2.RU]
    else:
        spk = target
    TW = []
    for t in held:
        a = ru.m.apply_tts(ssml_text=K3.text_for({"model": "ru", "pitch": "medium", "rate": "medium"}, t), speaker=spk, sample_rate=48000,
                           put_accent=True, put_yo=True)
        TW.append(a.numpy().copy())
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

    def measure(spe, ex, rate):
        W = []
        for t in held:
            a = L.say(spe, t, ex, rate)
            W.append(a.numpy().copy() if hasattr(a, "numpy") else np.asarray(a))
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

    def quality(W):
        mt, ut = [], []
        for j in (0, 2, 5):
            p = f"tmp/pq_{j}.wav"; g.save_wav(W[j], p)
            try:
                mt.append(SL.heard_match(p, held[j])[1]); ut.append(SL.utmos(SL.load(p, 16000)))
            except Exception:
                traceback.print_exc()
        return {"match": round(float(np.mean(mt)), 3) if mt else None, "utmos": round(float(np.mean(ut)), 2) if ut else None}

    tq = quality(TW)
    base_spe = L.base_rows[L.spe_key].double().numpy()
    base_ex = {keys["pp"]: L.base_rows[keys["pp"]].double().numpy(), keys["dp"]: L.base_rows[keys["dp"]].double().numpy(), "coef": L.base_rows.get("coef")}
    found = []
    for f in sorted(glob.glob(f"{OUT}/opt_{target}_*.json")):
        pr = json.load(open(f, encoding="utf-8"))
        found.append((os.path.basename(f)[:-5], np.array(pr["win"]["spe"], dtype=float), pr["win"]["score"]))
    found.sort(key=lambda x: -x[2])
    mans = [("основа", None, "medium")]
    for f in sorted(glob.glob(f"{OUT}/man_{target}_*.json")):
        pr = json.load(open(f, encoding="utf-8"))
        k, w = pr["keys"], pr["win"]
        mans.append((os.path.basename(f)[:-5], {k["pp"]: np.array(w["pp"]), k["dp"]: np.array(w["dp"]), "coef": float(w["coef"])}, pr["rate"]))
    log("тембров", [(n, round(s, 3)) for n, _, s in found], "манер", [m[0] for m in mans])
    Wb, mb = measure(base_spe, None, "medium")
    mb.update(quality(Wb))
    log("основа", mb)
    table = [{"spe": "основа", "man": "основа", "rate": "medium", **mb}]
    keep = {}
    for sn, spe, _ in found[:3]:
        for mn, ex, rate in mans:
            try:
                W, m = measure(spe, ex, rate)
            except Exception:
                traceback.print_exc(); continue
            m["J"] = round(m["close"] + 0.5 * m["man"], 4)
            table.append({"spe": sn, "man": mn, "rate": rate, **m})
            keep[(sn, mn)] = (W, spe, ex, rate)
            log(sn, mn, m)
    cand = sorted([r for r in table if "J" in r], key=lambda r: -r["J"])
    win = None
    for r in cand[:4]:
        r.update(quality(keep[(r["spe"], r["man"])][0]))
        log("качество", r["spe"], r["man"], r.get("match"), r.get("utmos"))
        if win is None and (r["match"] or 0) >= (mb["match"] or 0.9) - 0.07 and (r["utmos"] or 0) >= (mb["utmos"] or 3.0) - 0.45:
            win = r
    win = win or cand[0]
    W, spe, ex, rate = keep[(win["spe"], win["man"])]
    ex = ex or base_ex
    title, name, slot = NAME[target]
    out = {"target": target, "title": title, "name": name, "slot": slot, "held": held, "f0_target": round(f0t, 1), "target_quality": tq, "base": mb, "table": table,
           "win": {**{k: v for k, v in win.items()}, "pitch": L.pitch, "base_voice": sluh_opt.BASE[target][0], "spe_row": [round(float(v), 6) for v in spe],
                   "pp_row": [round(float(v), 6) for v in ex[keys["pp"]]], "dp_row": [round(float(v), 6) for v in ex[keys["dp"]]],
                   "coef": float(ex["coef"]) if ex.get("coef") is not None else None}}
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
    log("готово", target, "основа", mb["close"], "→", win["close"], "манера", mb["man"], "→", win["man"], win["spe"], win["man"], f"{total:.1f} с")


def merge():
    V, add = {}, []
    for f in sorted(glob.glob(f"{OUT}/proba_*.json")):
        p = json.load(open(f, encoding="utf-8")); w = p["win"]
        V[p["name"]] = {"slot": p["slot"], "spe": w["spe_row"], "pp": w["pp_row"], "dp": w["dp_row"], "coef": w["coef"], "rate": w["rate"], "pitch": w["pitch"],
                        "note": f"под {p['title']}: тембр {w['spe']}, манера {w['man']}; близость {w['close']} (основа {p['base']['close']})"}
        mix = {"w": "g03" if w["base_voice"] == "g03" else {r: {w["base_voice"]: 1.0} for r in ("dp", "pp", "spe")}, "spe_row": w["spe_row"], "pp_row": w["pp_row"],
               "dp_row": w["dp_row"], "coef": w["coef"], "pitch": w["pitch"], "rate": w["rate"]}
        if p["target"] == "n4":
            add.append({"name": "свой:№4", "group": "№4", "target": "n4@syn", "mix": mix, "kind": "mix", "note": "выращенный тембр и манера под №4"})
        else:
            hero, F = ("Барсик", 1.12) if p["target"] == "xenia" else ("Рон", 1.08)
            add.append({"name": f"свой:{p['target']}", "group": p["target"], "target": f"{p['target']}@syn", "mix": mix, "kind": "mix", "note": f"выращенный голос под {p['target']} (без движка)"})
            for Fk in (F, round(F - 0.04, 2), round(F + 0.04, 2)):
                add.append({"name": f"свой:{hero}:{Fk}", "group": hero, "target": f"{hero}@g24", "mix": mix, "F": Fk, "auto": True, "eq": False, "kind": "emu",
                            "note": f"выращенный голос + подделка движка, форманты ×{Fk}"})
    json.dump({"voices": V}, open(f"{OUT}/svoy_voices.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"voices": add}, open("sluh_add.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log("голоса:", list(V), "для слуха:", [a["name"] for a in add])


if __name__ == "__main__":
    merge() if sys.argv[1] == "merge" else main(sys.argv[1])
