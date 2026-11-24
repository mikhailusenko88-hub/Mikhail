#!/usr/bin/env python3
"""Свободный голос в МАНЕРЕ №4 (25.11.2026). Михаил снова выбрал №4 («первый вариант нравится больше всего»), но он на некоммерческой
модели и на канал не идёт. Прошлый поиск (svoy_free) мерил только тембр, высоту и темп. Здесь мерка — манера: ритм и мелодия.

Ритм — корреляция относительных длин слов с №4 на той же фразе; мелодия — корреляция высоты по словам. Плюс тембр (resemblyzer),
слова (whisper), естественность (UTMOS) и чистота произношения GOP (чем ближе к уровню №4, тем меньше акцента).
В модели v5_cis ритм задаёт строка dp, мелодию — pp, тембр — spe:
  r1: каждый из 32 дикторов по очереди в ритме (dp) и в мелодии (pp), остальное — от нашей лучшей смеси g03;
  r2: лучшие ритмы × лучшие мелодии, их смеси, три тембра.
  python svoy_manera.py r1 <part> <n> | pick | r2 <part> <n> | final   → cast9/itog.md, cast9/golos_manera.json, cast9/proba9.mp4
"""
import glob, json, math, os, shutil, subprocess, sys
import numpy as np
import svoy, svoy2, svoy_bars, svoy_omo
import svoy_kot3 as K3, svoy_lib as SL

PH = [svoy2.PHRASES[k][0] for k in (0, 1, 2, 3, 4, 5, 6, 8, 9, 10)]
LISTEN = (0, 2, 5, 6, 9)          # жираф, кит, «Ты видел снег…?», кот Барсик, замок — как в прошлых пробах
SPE = [{"ru_nash2": 0.82, "ru_kejilgan": 0.18},                       # g03 — чище всех
       {"ru_nash2": 0.58, "ru_eduard": 0.29, "ru_kejilgan": 0.12},    # g02 — похожесть тембра 0,87
       {"ru_nash1": 0.80, "ru_alexandr": 0.20}]                       # g22 — похожесть 0,875
PITCH, RATE = "low", "medium"
log = svoy.log


def base():
    return json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]["ru_svoy1"]["w"]


def pool():
    return sorted(json.load(open("cast/kasting.json", encoding="utf-8"))["cast"])


def cands1():
    b = base()
    r13 = json.load(open("cast2/krug2.json", encoding="utf-8"))["light"]["r13"]["w"]
    C = [{"id": "b_g03", "w": b, "note": "наша лучшая смесь"},
         {"id": "b_nash3", "w": {r: {"ru_nash3": 1.0} for r in ("dp", "pp", "spe")}, "note": "сейчас в «Почему так?»"},
         {"id": "b_r13", "w": r13, "note": "«Новый 2»"}]
    for s in pool():
        C.append({"id": f"d_{s[3:]}", "w": {"dp": {s: 1.0}, "pp": b["pp"], "spe": b["spe"]}, "role": "dp", "spk": s})
        C.append({"id": f"p_{s[3:]}", "w": {"dp": b["dp"], "pp": {s: 1.0}, "spe": b["spe"]}, "role": "pp", "spk": s})
    return C


def meas(path, plain):
    a = SL.load(path, SL.SR16)
    words, q = SL.ali(a, plain)
    pt, f0 = SL.pitch(a)
    D, M = SL.word_vecs(words, pt, f0)
    heard, mt = SL.heard_match(path, plain)
    return {"a": a, "D": D, "M": M, "gop": q["gop"], "match": mt, "heard": heard, "ut": SL.utmos(a), "f": SL.feats(a, plain)}


def target(save_ref):
    """№4 читает те же фразы с той же разметкой кусков — мерка (в итоговый звук не идёт, только в ролик для сравнения)."""
    import gen as g
    cfg = {"model": "ru", "pitch": "medium", "rate": "medium"}
    net = svoy2.Net(svoy2.RU)
    net.put(net.build(svoy_bars.W4))
    T = []
    for k, plain in enumerate(PH):
        p = f"tmp/T4_{k:02d}.wav"
        a = net.m.apply_tts(ssml_text=K3.text_for(cfg, plain), speaker=svoy2.SLOT[svoy2.RU], sample_rate=48000, put_accent=True, put_yo=True)
        g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
        m = meas(p, plain); T.append(m)
        if save_ref and k in LISTEN:
            listen(p, plain, f"pack/T4__{k:02d}.flac")
    info = {"emb": SL.emb([m["a"] for m in T]).tolist(), "f0": float(np.median([m["f"]["f0"] for m in T])),
            "rate": float(np.median([m["f"]["rate"] for m in T])), "range": float(np.median([m["f"]["range"] for m in T])),
            "gop": float(np.mean([m["gop"] for m in T])), "utmos": float(np.mean([m["ut"] for m in T])), "match": float(np.mean([m["match"] for m in T]))}
    if save_ref:
        json.dump(info, open("pack/target.json", "w"))
    del net
    return T, info


def listen(wav, plain, flac):
    """Запись для ролика: у вопроса без вопросительного слова — мелодия бота (выбор Михаила)."""
    import gen as g
    q = "tmp/_q.wav"; shutil.copy(wav, q)
    if K3.yesno(plain):
        try:
            g.qvrise(q, win=min(0.48, 0.22 + 0.10 * K3.last_syll(plain)))
        except Exception as e:
            log("мелодия вопроса не легла:", repr(e))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", q, flac], check=True)


def J(r, T):
    dst = abs(12 * math.log2(max(r["f0"], 1) / T["f0"]))
    return round(1.5 * r["rhythm"] + 1.5 * r["melody"] + 2 * r["sim"] + 2 * r["match"] + 0.6 * r["utmos"] + 2 * r["gop"] - 0.15 * dst, 3)


def evaluate(C, tag, save_ref=False):
    import gen as g
    for d in ("pack", "tmp"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    T, info = target(save_ref)
    log("мерка №4:", {k: round(v, 3) for k, v in info.items() if k != "emb"})
    temb = np.array(info["emb"])
    cfg = {"model": "cis", "pitch": PITCH, "rate": RATE}
    texts = {p: K3.text_for(cfg, p) for p in PH}
    log("разметка:", texts[PH[6]][:200])
    net = svoy2.Net(svoy2.CIS)
    for c in C:
        try:
            net.put(net.build(c["w"]))
            R = []
            for k, plain in enumerate(PH):
                p = f"tmp/{c['id']}_{k:02d}.wav"
                a = net.m.apply_tts(ssml_text=texts[plain], speaker=svoy2.SLOT[svoy2.CIS], sample_rate=48000)
                g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
                m = meas(p, plain); m.update(SL.manner(m["D"], m["M"], T[k]["D"], T[k]["M"])); R.append(m)
                if k in LISTEN:
                    listen(p, plain, f"pack/M__{c['id']}__{k:02d}.flac")
            mean = lambda key: float(np.mean([x[key] for x in R if x[key] is not None])) if any(x[key] is not None for x in R) else 0.0
            r = dict({k: v for k, v in c.items()}, tag=tag, rhythm=round(mean("rhythm"), 3), melody=round(mean("melody"), 3),
                     sim=round(float(np.dot(SL.emb([x["a"] for x in R]), temb)), 4), match=round(mean("match"), 3), utmos=round(mean("ut"), 3),
                     gop=round(mean("gop"), 4), f0=round(float(np.median([x["f"]["f0"] for x in R])), 1),
                     rate=round(float(np.median([x["f"]["rate"] for x in R])), 2), range=round(float(np.median([x["f"]["range"] for x in R])), 2),
                     bad=[(PH[k], x["heard"]) for k, x in enumerate(R) if x["match"] < 0.85])
            r["J"] = J(r, info)
            json.dump(r, open(f"pack/L_{c['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
            log(c["id"], "J", r["J"], "ритм", r["rhythm"], "мелодия", r["melody"], "тембр", r["sim"], "слова", r["match"], "UTMOS", r["utmos"],
                "GOP", r["gop"], "Гц", r["f0"], "темп", r["rate"])
        except Exception as e:
            import traceback
            log("ОШИБКА", c["id"], repr(e)); traceback.print_exc()


def loadL():
    return {os.path.basename(j)[2:-5]: json.load(open(j, encoding="utf-8")) for j in glob.glob("pack/L_*.json")}


def pick():
    L = loadL()
    b = L.get("b_g03", {"match": 0.9, "gop": 0})
    ok = lambda r: r["match"] >= b["match"] - 0.04 and r["gop"] >= b["gop"] - 0.03
    dp = sorted([r for r in L.values() if r.get("role") == "dp" and ok(r)], key=lambda r: -r["rhythm"])
    pp = sorted([r for r in L.values() if r.get("role") == "pp" and ok(r)], key=lambda r: -r["melody"])
    for r in dp[:6]:
        log("ритм:", r["spk"], r["rhythm"], "слова", r["match"], "GOP", r["gop"], "UTMOS", r["utmos"])
    for r in pp[:6]:
        log("мелодия:", r["spk"], r["melody"], "слова", r["match"], "GOP", r["gop"], "UTMOS", r["utmos"])
    D = [r["spk"] for r in dp[:4]]; P = [r["spk"] for r in pp[:4]]
    C = []
    for i, d in enumerate(D):
        for j, p in enumerate(P):
            C.append({"id": f"x{i}{j}", "w": {"dp": {d: 1.0}, "pp": {p: 1.0}, "spe": SPE[0]}})
    eq = lambda xs: {s: round(1 / len(xs), 3) for s in xs}
    for i, dd in enumerate((D[:2], D[:3])):
        for j, pp_ in enumerate((P[:2], P[:3])):
            C.append({"id": f"m{i}{j}", "w": {"dp": eq(dd), "pp": eq(pp_), "spe": SPE[0]}})
    for i, (d, p) in enumerate(((D[0], P[0]), (D[0], P[1 % len(P)]), (D[1 % len(D)], P[0]))):
        for s in (1, 2):
            C.append({"id": f"s{i}{s}", "w": {"dp": {d: 1.0}, "pp": {p: 1.0}, "spe": SPE[s]}})
    json.dump(C, open("pack/round2.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("круг 2:", len(C), "ритмы", D, "мелодии", P)


def final():
    os.makedirs("cast9", exist_ok=True)
    L = loadL()
    T = json.load(open("pack/target.json"))
    fmt = lambda w: "; ".join(f"{r}: " + " + ".join(f"{s.replace('ru_', '')} {x:.2f}" for s, x in sorted(v.items(), key=lambda z: -z[1])) for r, v in w.items())
    top = sorted(L.values(), key=lambda r: -r["J"])
    Lm = ["# Свободный голос в манере №4 (v5_cis, MIT)", "",
          f"Мерка — №4: {T['f0']:.0f} Гц, темп {T['rate']:.1f} слога/с, слова {T['match']:.3f}, UTMOS {T['utmos']:.2f}, GOP {T['gop']:.3f}.",
          "Ритм и мелодия — корреляция с №4 по словам на тех же фразах (1 — совпадает). GOP — чистота произношения.",
          "J = 1,5·ритм + 1,5·мелодия + 2·тембр + 2·слова + 0,6·UTMOS + 2·GOP − 0,15·разница высоты (полутоны).", "",
          "| | смесь | J | ритм | мелодия | тембр | слова | UTMOS | GOP | Гц | темп | состав |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top[:30], 1):
        Lm.append(f"| {i} | {r['id']} {r.get('note', '')} | {r['J']} | {r['rhythm']} | {r['melody']} | {r['sim']} | {r['match']} | {r['utmos']} | "
                  f"{r['gop']} | {r['f0']:.0f} | {r['rate']} | {fmt(r['w'])} |")
    for role, key, name in (("dp", "rhythm", "Ритм (dp) каждого диктора"), ("pp", "melody", "Мелодия (pp) каждого диктора")):
        Lm += ["", f"## {name}", "", "| диктор | " + ("ритм" if key == "rhythm" else "мелодия") + " | слова | UTMOS | GOP |", "|---|---|---|---|---|"]
        for r in sorted([r for r in L.values() if r.get("role") == role], key=lambda r: -r[key]):
            Lm.append(f"| {r['spk']} | {r[key]} | {r['match']} | {r['utmos']} | {r['gop']} |")
    open("cast9/itog.md", "w", encoding="utf-8").write("\n".join(Lm) + "\n")
    log("\n".join(Lm[:22]))
    b = L.get("b_g03")
    new = [r for r in top if not r["id"].startswith("b_") and r["match"] >= (b["match"] - 0.03 if b else 0.9)][:2]
    json.dump({"made": "2026-11-25", "model": "v5_cis_base (MIT)", "pitch": PITCH, "rate": RATE,
               "voices": {f"ru_manera{i}": {"w": r["w"], "J": r["J"], "rhythm": r["rhythm"], "melody": r["melody"], "sim": r["sim"],
                                            "match": r["match"], "utmos": r["utmos"], "gop": r["gop"]} for i, r in enumerate(new, 1)}},
              open("cast9/golos_manera.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"target": {k: v for k, v in T.items() if k != "emb"}, "all": top}, open("cast9/manera.json", "w", encoding="utf-8"), ensure_ascii=False)
    vp = [("№4 — образец", "T4", "как понравился (не свободный)")]
    if b:
        vp.append(("Свободный — как в прошлой пробе", "M__b_g03", f"ритм {b['rhythm']:.2f}, мелодия {b['melody']:.2f}"))
    for i, r in enumerate(new, 1):
        vp.append((f"Свободный — в манере №4, вариант {i}", f"M__{r['id']}", f"ритм {r['rhythm']:.2f}, мелодия {r['melody']:.2f}"))
    import svoy_kot as K1
    svoy2.video(vp, "cast9/proba9.mp4", [(t, k in LISTEN) for k, t in enumerate(PH)])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "tmp/all.wav", "-c:a", "libmp3lame", "-b:a", "160k", "cast9/proba9.mp3"], check=True)
    K1.check_file("cast9/proba9.mp4")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "r1":
        p, n = int(sys.argv[2]), int(sys.argv[3]); evaluate(cands1()[p::n], "1", save_ref=(p == 0))
    elif cmd == "pick":
        pick()
    elif cmd == "r2":
        p, n = int(sys.argv[2]), int(sys.argv[3]); evaluate(json.load(open("r2in/round2.json", encoding="utf-8"))[p::n], "2")
    elif cmd == "final":
        final()
