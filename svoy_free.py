#!/usr/bin/env python3
"""№4 на свободной модели (24.11.2026). Михаил: платную лицензию не берём, «чтобы мы не платили потом нигде».
№4 собран на модели Барсика (Silero v5_ru, CC BY-NC) — смешивание не меняет её лицензию. Делаем голос, звучащий как №4,
целиком на модели v5_cis (MIT). №4 здесь — только мерка для сравнения (в готовый звук не попадает).

Кандидат = доли дикторов v5_cis в ритме (dp), мелодии (pp), тембре (spe) + высота и темп через SSML модели.
Оценка: похожесть тембра на №4 (resemblyzer), высота, темп и живость как у №4, разборчивость, естественность.
  python svoy_free.py r1 <part> <n>   круг 1 (64 кандидата)
  python svoy_free.py pick            лучшие → круг 2
  python svoy_free.py r2 <part> <n>
  python svoy_free.py final           cast7/itog.md, cast7/golos_free.json, cast7/proba7.mp4
"""
import difflib, glob, json, os, random, re, shutil, subprocess, sys
import numpy as np
import svoy, svoy2, svoy_bars, svoy_omo

PH = [t for t, _ in svoy2.PHRASES]
LISTEN = {0, 2, 5, 6, 10}
MALE_LOW = ["ru_safarhuja", "ru_kejilgan", "ru_roman", "ru_miyau", "ru_nash2", "ru_alexandr", "ru_nash1", "ru_bogdan", "ru_eduard"]
PITCH = ["medium", "low", "x-low"]
RATE = ["medium", "fast"]


def mark_full(plain):
    """Для v5_cis: «+» во всех словах (ruaccent), омографы — по своим правилам svoy_omo.RULES поверх словаря."""
    import voice_check as vc
    ws = vc.tokenize(plain)
    vc.accentize(plain, ws)
    toks = re.findall(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*|[^А-Яа-яЁё]+", plain)
    out, i = [], 0
    for tok in toks:
        if re.match(r"[А-Яа-яЁё]", tok):
            w = ws[i]
            prev = ws[i - 1]["w"] if i > 0 and not re.search(r"[.!?…,;:—–]", ws[i - 1]["punct"]) else ""
            nxt = ws[i + 1]["w"] if i + 1 < len(ws) and not re.search(r"[.!?…,;:—–]", w["punct"]) else ""
            left = " ".join(x["w"] for x in ws[max(0, i - 4):i])
            i += 1
            e = w["exp"]
            f = svoy_omo.RULES.get(w["w"])
            if f is not None:
                e2 = f(prev, nxt, left) if f is svoy_omo._r_ruki else f(prev, nxt)
                if e2 is not None:
                    e = e2
            if len(w["vows"]) == 1:
                e = None if w["w"] in svoy.CLIT else 0
            if e is not None and w["vows"]:
                k = -1; t2 = ""
                for c in tok:
                    if c.lower() in vc.VOW:
                        k += 1
                        if k == e:
                            t2 += "+"
                    t2 += c
                tok = t2
        out.append(tok)
    return "".join(out)


_enc = {}


def spk_emb(paths):
    if "e" not in _enc:
        from resemblyzer import VoiceEncoder
        _enc["e"] = VoiceEncoder("cpu")
    from resemblyzer import preprocess_wav
    E = [_enc["e"].embed_utterance(preprocess_wav(p)) for p in paths]
    m = np.mean(E, 0)
    return m / np.linalg.norm(m)


def stats(paths, texts):
    import voice_check as vc
    f0s, rng, rates = [], [], []
    for p, t in zip(paths, texts):
        a = vc.load16(p)
        P = vc.prosody(a)
        fv = P[2][P[2] > 0]
        if len(fv) > 10:
            s = [vc.st(x) for x in fv]
            f0s.append(float(np.median(fv))); rng.append(float(np.percentile(s, 95) - np.percentile(s, 5)))
        fr = a[: len(a) // 320 * 320].reshape(-1, 320)
        rms = np.sqrt((fr ** 2).mean(1) + 1e-12)
        act = (rms > rms.max() * 10 ** (-35 / 20)).sum() * 0.02
        rates.append(sum(1 for c in t.lower() if c in "аеёиоуыэюя") / max(act, 0.1))
    return {"f0": float(np.median(f0s)), "range": float(np.mean(rng)), "rate": float(np.mean(rates))}


def target():
    """№4 читает те же фразы — мерка (пишется только в tmp/, в итог и в ролик не идёт, кроме сравнения на слух)."""
    os.makedirs("tmp/t", exist_ok=True)
    net = svoy2.Net(svoy2.RU)
    rows = net.build(svoy_bars.W4); net.put(rows)
    import gen as g
    paths = []
    for k, t in enumerate(PH):
        p = f"tmp/t/{k:02d}.wav"
        a = net.m.apply_tts(text=svoy_omo.omo_marks(t)[0], speaker=svoy2.SLOT[svoy2.RU], sample_rate=48000,
                            put_accent=True, put_yo=True)
        g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
        paths.append(p)
    T = stats(paths, PH)
    T["emb"] = spk_emb(paths).tolist()
    del net
    return T, paths


def J(r, T):
    import math
    dst = abs(12 * math.log2(max(r["f0"], 1) / T["f0"]))
    s = 3 * r["sim"] + 2 * r["match"] + 0.6 * r["utmos"] - 0.2 * dst - 0.3 * abs(r["rate"] - T["rate"]) - 0.05 * abs(r["range"] - T["range"])
    return round(s, 3)


def cands1():
    rng = random.Random(2411)
    cast = json.load(open("cast/kasting.json", encoding="utf-8"))["cast"]
    good = sorted(cast, key=lambda s: -cast[s]["score"])[:18]
    r13 = json.load(open("cast2/krug2.json", encoding="utf-8"))["light"]["r13"]["w"]
    C = [{"id": "f00", "w": {r: {"ru_nash2": 1.0} for r in ("dp", "pp", "spe")}, "pitch": "medium", "srate": "medium", "note": "nash2"},
         {"id": "f01", "w": r13, "pitch": "medium", "srate": "medium", "note": "Новый 2"},
         {"id": "f02", "w": r13, "pitch": "x-low", "srate": "fast", "note": "Новый 2 ниже и быстрее"}]
    for i in range(3, 64):
        w = {}
        for role, pool, kmax in (("dp", good, 3), ("pp", good, 3), ("spe", MALE_LOW, 2)):
            pick = rng.sample(pool, rng.randint(1, kmax))
            ds = np.random.default_rng(rng.randint(0, 10 ** 6)).dirichlet([1.0] * len(pick))
            w[role] = {s: round(float(d), 3) for s, d in zip(pick, ds) if d >= 0.05}
        C.append({"id": f"f{i:02d}", "w": w, "pitch": rng.choices(PITCH, [0.2, 0.4, 0.4])[0],
                  "srate": rng.choices(RATE, [0.5, 0.5])[0]})
    return C


def evaluate(C, tag):
    import torch, voice_check as vc
    os.makedirs("pack", exist_ok=True)
    svoy_omo.ruacc()              # настоящий ruaccent (для омографов №4) — до подмены
    svoy2.patch_ruaccent()
    T, tpaths = target()
    for k in LISTEN:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tpaths[k], f"pack/T4__{k:02d}.flac"], check=True)
    json.dump({x: T[x] for x in ("f0", "range", "rate")}, open("pack/target.json", "w"))
    svoy.log("мерка №4:", {x: round(T[x], 2) for x in ("f0", "range", "rate")})
    marks = {t: mark_full(t) for t in PH}
    svoy.log("разметка:", marks[PH[10]])
    net = svoy2.Net(svoy2.CIS)
    temb = np.array(T["emb"])
    import gen as g
    for c in C:
        try:
            rows = net.build(c["w"]); net.put(rows)
            paths, res = [], []
            for k, t in enumerate(PH):
                p = f"tmp/{c['id']}_{k:02d}.wav"
                ssml = f'<speak><prosody rate="{c["srate"]}" pitch="{c["pitch"]}">{marks[t]}</prosody></speak>'
                a = net.m.apply_tts(ssml_text=ssml, speaker=svoy2.SLOT[svoy2.CIS], sample_rate=48000)
                g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
                paths.append(p)
                a16 = vc.load16(p)
                with torch.no_grad():
                    ut = float(vc.utmos_model()(torch.from_numpy(a16)[None], vc.SR))
                heard = vc.whisper_model().transcribe(p, language="ru", fp16=False)["text"]
                res.append((ut, difflib.SequenceMatcher(None, vc.norm_words(t), vc.norm_words(heard)).ratio(), heard))
                if k in LISTEN:
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/{c['id']}__{k:02d}.flac"], check=True)
            S = stats(paths, PH)
            r = dict(c, tag=tag, sim=round(float(np.dot(spk_emb(paths), temb)), 4),
                     utmos=round(float(np.mean([x[0] for x in res])), 3), match=round(float(np.mean([x[1] for x in res])), 3),
                     f0=round(S["f0"], 1), range=round(S["range"], 2), rate=round(S["rate"], 2),
                     bad=[(PH[k], x[2]) for k, x in enumerate(res) if x[1] < 0.85])
            r["J"] = J(r, T)
            json.dump(r, open(f"pack/L_{c['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
            svoy.log(c["id"], "J", r["J"], "похожесть", r["sim"], "Гц", r["f0"], "темп", r["rate"], "UTMOS", r["utmos"],
                     "слова", r["match"], c["pitch"], c["srate"], c["w"])
        except Exception as e:
            import traceback
            svoy.log("ОШИБКА", c["id"], repr(e)); traceback.print_exc()


def loadL():
    return {os.path.basename(j)[2:-5]: json.load(open(j, encoding="utf-8")) for j in glob.glob("pack/L_*.json")}


def pick():
    L = sorted(loadL().values(), key=lambda r: -r["J"])
    rng = random.Random(2412)
    cast = json.load(open("cast/kasting.json", encoding="utf-8"))["cast"]
    good = sorted(cast, key=lambda s: -cast[s]["score"])[:18]
    C = []
    for j, r in enumerate(L[:6]):
        svoy.log("круг 1:", r["id"], r["J"], r["sim"], r["f0"], r["rate"], r["pitch"], r["srate"], r["w"])
        for i in range(4):
            w = {k: dict(v) for k, v in r["w"].items()}
            if i < 3:
                role = ("dp", "pp", "spe")[i]
                w[role] = svoy2.jitter(w[role], MALE_LOW if role == "spe" else good, rng, keep=(0.7, 0.9), kmax=1)
                pitch, srate = r["pitch"], r["srate"]
            else:
                pitch = PITCH[min(2, PITCH.index(r["pitch"]) + 1)] if r["f0"] > 92 else r["pitch"]
                srate = "fast" if r["rate"] < 6.0 else r["srate"]
            C.append({"id": f"g{j}{i}", "w": w, "pitch": pitch, "srate": srate, "from": r["id"]})
    json.dump(C, open("pack/round2.json", "w", encoding="utf-8"), ensure_ascii=False)


def final():
    os.makedirs("cast7", exist_ok=True)
    L = loadL()
    T = json.load(open("pack/target.json"))
    top = sorted(L.values(), key=lambda r: -r["J"])
    fmt = lambda w: "; ".join(f"{r}: " + " + ".join(f"{s.replace('ru_', '')} {x:.2f}" for s, x in sorted(v.items(), key=lambda z: -z[1])) for r, v in w.items())
    Lm = ["# №4 на свободной модели (v5_cis, MIT)", "",
          f"Мерка — №4 (модель Барсика): {T['f0']:.0f} Гц, темп {T['rate']:.1f} слога/с, живость {T['range']:.1f} полутона.",
          "J = 3·похожесть тембра + 2·слова + 0,6·UTMOS − 0,2·разница высоты (полутоны) − 0,3·разница темпа − 0,05·разница живости.", "",
          "| | кандидат | J | похожесть на №4 | Гц | темп | живость | UTMOS | слова | высота/темп SSML | состав |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top[:25], 1):
        Lm.append(f"| {i} | {r['id']} {r.get('note', '')} | {r['J']} | {r['sim']} | {r['f0']:.0f} | {r['rate']} | {r['range']} | "
                  f"{r['utmos']} | {r['match']} | {r['pitch']}/{r['srate']} | {fmt(r['w'])} |")
    open("cast7/itog.md", "w", encoding="utf-8").write("\n".join(Lm) + "\n")
    svoy.log("\n".join(Lm[:14]))
    best = top[:3]
    json.dump({"made": "2026-11-24", "model": "v5_cis_base (MIT)", "how": "доли дикторов в dp/pp/spe + SSML prosody",
               "voices": {f"ru_svoy{i}": {"w": r["w"], "pitch": r["pitch"], "rate_ssml": r["srate"], "J": r["J"], "sim": r["sim"]}
                          for i, r in enumerate(best, 1)}},
              open("cast7/golos_free.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pick_ = [("№4 — как понравился (модель Барсика)", "T4", "мерка, не свободный")]
    for i, r in enumerate(best, 1):
        pick_.append((f"Свободный {i}", r["id"], f"похожесть {r['sim']:.2f}, естественность {r['utmos']:.2f}"))
    ph = [(t, k in LISTEN) for k, t in enumerate(PH)]
    svoy2.video(pick_, "cast7/proba7.mp4", ph)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "r1":
        p, n = int(sys.argv[2]), int(sys.argv[3]); evaluate(cands1()[p::n], "1")
    elif cmd == "pick":
        pick()
    elif cmd == "r2":
        p, n = int(sys.argv[2]), int(sys.argv[3]); evaluate(json.load(open("pack/round2.json", encoding="utf-8"))[p::n], "2")
    elif cmd == "final":
        final()
