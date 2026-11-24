#!/usr/bin/env python3
"""«Кот Барсик», круг 2 (24.11.2026). Круг 1 показал: с «+» гласная в «кот» у всех голосов полная («о», без «+» — «кат»),
но слово в «кот Барсик» длится всего 0,12–0,14 с и склеивается с «Барсик» («котбарсик»); перед паузой («наш кот,») — 0,18–0,24 с.
Здесь: сколько длится такое слово у эталонных голосов, и как его вытянуть.

«Стык» — короткое неслужебное слово прямо перед ударным слогом следующего слова, без знака между ними.
Варианты у свободных голосов (v5_cis, SSML): a — как было; e — слово на стыке отдельным куском, темп slow; f — x-slow;
g — slow и на ступень выше тоном; h — вся фраза без ускорения + слово slow.
У №4 (v5_ru): a — как было; s — то же через SSML (проверка); e, f — слово на стыке slow / x-slow.
Эталоны (только для замера): RK — Ксения (v5_ru), RA — Альбина, RN — nash3 (нынешний голос «Почему так?»).
  python svoy_kot2.py gen <V4|F1|F2|F3|RK|RC>
  python svoy_kot2.py final ["V4=a,F1=e,F2=e,F3=e"]     cast8/itog2.md, cast8/proba8.mp4, cast8/proba8.mp3
"""
import difflib, json, os, re, subprocess, sys
import numpy as np
import svoy, svoy2, svoy_bars, svoy_omo, svoy_free
import svoy_kot as K1

PH = K1.PH
NL = len(K1.LISTEN_PH)
UP = {"x-low": "low", "low": "medium", "medium": "high", "high": "x-high"}
NAMES = {"a": "как было", "s": "как было, через SSML", "e": "слово на стыке — slow", "f": "слово на стыке — x-slow",
         "g": "слово на стыке — slow и выше тоном", "h": "вся фраза без ускорения + слово slow"}
log = svoy.log


def voices():
    V = dict(K1.voices())
    V["V4"] = dict(V["V4"], vars="asef")
    for k in ("F1", "F2", "F3"):
        V[k] = dict(V[k], vars="aefgh")
    V["RK"] = {"model": "ru", "speaker": "kseniya", "vars": "a", "ref": True}
    V["RA"] = {"model": "cis", "speaker": "ru_albina", "pitch": "medium", "srate": "medium", "vars": "a", "ref": True}
    V["RN"] = {"model": "cis", "w": {r: {"ru_nash3": 1.0} for r in ("dp", "pp", "spe")}, "pitch": "medium", "srate": "medium",
               "vars": "a", "ref": True}
    return V


JOBS = {"V4": ["V4"], "F1": ["F1"], "F2": ["F2"], "F3": ["F3"], "RK": ["RK"], "RC": ["RA", "RN"]}


def chunks_ssml(chunks, pitch, rate, srate, spitch=None):
    return "<speak>" + "".join(f'<prosody rate="{srate if s else rate}" pitch="{(spitch or pitch) if s else pitch}">{t}</prosody>'
                               for t, s in chunks) + "</speak>"


def clash_chunks2(target, full):
    """Куски по тексту target; где стык — определяем по полностью размеченному full (в target «+» стоит не везде)."""
    tt, tf = K1.WORD.findall(target), K1.WORD.findall(full)
    if len(tt) != len(tf):
        return [(target, False)]
    words = [(i, t) for i, t in enumerate(tf) if K1.isword(t)]
    slow = set()
    for (i, t), (j, t2) in zip(words, words[1:]):
        if not K1.content_mono(t) or re.search(r"[.!?…,;:—–]", "".join(tf[i + 1:j])):
            continue
        k = t2.find("+")
        if (k >= 0 and K1.nv(t2[:k]) == 0) or K1.content_mono(t2):
            slow.add(i)
    chunks, cur = [], ""
    for i, t in enumerate(tt):
        if i in slow:
            if cur.strip():
                chunks.append((cur, False)); cur = ""
            chunks.append((cur + t, True)); cur = ""          # пробел между двумя такими словами — внутрь куска, не отдельным
        else:
            cur += t
    if cur.strip():
        chunks.append((cur, False))
    return chunks


def text_for(v, var, plain):
    """→ (текст, это SSML?)"""
    if v["model"] == "ru":
        base = svoy_omo.omo_marks(plain)[0]
        if v.get("ref") or var == "a":
            return base, False
        m = K1.mono_plus(base)
        if var == "s":
            return K1.ssml(m, "medium", "medium"), True
        return chunks_ssml(clash_chunks2(m, svoy_free.mark_full(plain)), "medium", "medium", {"e": "slow", "f": "x-slow"}[var]), True
    full = svoy_free.mark_full(plain)
    p, r = v["pitch"], v["srate"]
    if var == "a":
        return K1.ssml(full, p, r), True
    ch = clash_chunks2(full, full)
    if var == "e":
        return chunks_ssml(ch, p, r, "slow"), True
    if var == "f":
        return chunks_ssml(ch, p, r, "x-slow"), True
    if var == "g":
        return chunks_ssml(ch, p, r, "slow", UP[p]), True
    return chunks_ssml(ch, p, "medium", "slow"), True


def measure(path, plain):
    import torch, voice_check as vc
    a = vc.load16(path)
    with torch.no_grad():
        ut = float(vc.utmos_model()(torch.from_numpy(a)[None], vc.SR))
    heard = vc.whisper_model().transcribe(path, language="ru", fp16=False)["text"]
    nw = lambda t: vc.norm_words(t.replace("-", " "))          # «кот-барсик» у распознавателя — это орфография, не ошибка
    ref, hw = nw(plain), nw(heard)
    sm = difflib.SequenceMatcher(None, ref, hw)
    ok = set()
    for blk in sm.get_matching_blocks():
        ok.update(range(blk.a, blk.a + blk.size))
    words = vc.tokenize(plain)
    vc.accentize(plain, words)
    vowels = vc.align(a, words)
    _, pt, f0, itx, iv = vc.prosody(a)
    vst = np.array([vc.st(x) for x in f0[f0 > 0]]) if (f0 > 0).any() else np.array([0.0])
    med_st = float(np.median(vst))
    loud = iv[iv > iv.max() - 30]
    med_i = float(np.median(loud))
    syl = float(len(loud) * 0.01 / max(len(vowels), 1))              # средняя длина слога (по времени речи)
    rows = []
    for wi, w in enumerate(words):
        if len(w["vows"]) != 1 or w["w"] in svoy.CLIT or "t0" not in w:
            continue
        nx = words[wi + 1] if wi + 1 < len(words) else None
        clash = bool(nx) and not w["punct"] and (nx["exp"] == 0) and nx["w"] not in svoy.CLIT
        t0, t1 = w["t0"], w["t1"]
        ff = f0[(pt >= t0 - 0.02) & (pt <= t1 + 0.02) & (f0 > 0)]
        ii = iv[(itx >= t0 - 0.01) & (itx <= t1 + 0.01)]
        r = {"w": w["w"], "L": w["vows"][0], "clash": clash, "heard_ok": wi in ok, "wdur": round(t1 - t0, 3),
             "rel": round((t1 - t0) / syl, 2) if syl else None,
             "dst": round(float(np.median([vc.st(x) for x in ff])) - med_st, 1) if len(ff) else None,
             "dI": round(float(ii.max()) - med_i, 1) if len(ii) else None,
             "gap": round(nx["t0"] - t1, 3) if nx and "t0" in nx else None}
        v = next((x for x in vowels if x["w"] == wi), None)
        if v and r["L"] in vc.QSETS:
            full, red = vc.QSETS[r["L"]]
            r["full"] = round(sum(p for t, p in v["pt"].items() if t in full), 3)
            r["red"] = round(sum(p for t, p in v["pt"].items() if t in red), 3)
        if v:
            r["top"] = v["ph"]
        rows.append(r)
    return {"utmos": round(ut, 3), "heard": heard.strip(), "match": round(sm.ratio(), 3), "dur": round(len(a) / vc.SR, 2),
            "syl": round(syl, 3), "mono": rows}


def gen(job):
    import gen as g
    os.makedirs("pack", exist_ok=True); os.makedirs("tmp", exist_ok=True)
    V = voices()
    svoy_omo.ruacc()
    svoy2.patch_ruaccent()
    net = None
    for vk in JOBS[job]:
        v = V[vk]
        mid = svoy2.RU if v["model"] == "ru" else svoy2.CIS
        if net is None or net.mid != mid:
            net = svoy2.Net(mid)
        if "w" in v:
            net.put(net.build(v["w"])); sp = svoy2.SLOT[mid]
        else:
            sp = v["speaker"]
        res = {}
        for var in v["vars"]:
            recs = []
            try:
                for k, plain in enumerate(PH):
                    text, is_ssml = text_for(v, var, plain)
                    p = f"tmp/K2__{vk}{var}__{k:02d}.wav"
                    if is_ssml:
                        try:
                            a = net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True) \
                                if v["model"] == "ru" else net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000)
                        except TypeError:
                            a = net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000)
                    else:
                        a = net.m.apply_tts(text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
                    g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
                    r = measure(p, plain); r["sent"] = text; r["k"] = k
                    recs.append(r)
                    if k < NL and not v.get("ref"):
                        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/K2__{vk}{var}__{k:02d}.flac"], check=True)
                    cl = [(m["w"], m["wdur"], m["rel"], m.get("dst"), m.get("top")) for m in r["mono"] if m["clash"]]
                    log(f"{vk}{var} {k:02d} UTMOS {r['utmos']} слова {r['match']} {r['dur']} с | {r['heard']} | стык: {cl}")
                res[var] = recs
            except Exception as e:
                import traceback
                log("ОШИБКА", vk, var, repr(e)); traceback.print_exc()
        json.dump(res, open(f"pack/K2_{vk}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def stat(recs):
    cl = [m for r in recs for m in r["mono"] if m["clash"]]
    oo = [m for m in cl if "full" in m]
    mean = lambda xs: round(float(np.mean(xs)), 3) if len(xs) else None
    return {"n": len(cl), "wdur": mean([m["wdur"] for m in cl]), "rel": mean([m["rel"] for m in cl if m["rel"] is not None]),
            "dst": mean([m["dst"] for m in cl if m["dst"] is not None]), "dI": mean([m["dI"] for m in cl if m["dI"] is not None]),
            "gap": mean([m["gap"] for m in cl if m["gap"] is not None]),
            "full": mean([m["full"] > m["red"] for m in oo]), "heard": mean([m["heard_ok"] for m in cl]),
            "match": mean([r["match"] for r in recs]), "utmos": mean([r["utmos"] for r in recs]),
            "dur": round(float(sum(r["dur"] for r in recs)), 1)}


def final(choice=None):
    os.makedirs("cast8", exist_ok=True)
    V = voices()
    D, S = {}, {}
    for vk in V:
        f = f"pack/K2_{vk}.json"
        if os.path.exists(f):
            D[vk] = json.load(open(f, encoding="utf-8"))
            S[vk] = {var: stat(recs) for var, recs in D[vk].items() if recs}
    refs = [S[k]["a"] for k in ("RK", "RA", "RN") if k in S and "a" in S[k]]
    target = float(np.mean([r["rel"] for r in refs])) if refs else 1.0      # сколько слогов средней длины длится слово на стыке у эталонов
    best = {}
    for vk in ("V4", "F1", "F2", "F3"):
        if vk not in S:
            continue
        a = S[vk].get("a")
        cand = {var: s for var, s in S[vk].items() if var != "s" and s["rel"] is not None and
                (a is None or (s["utmos"] >= a["utmos"] - 0.1 and s["match"] >= a["match"] - 0.03))}
        cand = cand or S[vk]
        best[vk] = min(cand, key=lambda var: abs(np.log(max(cand[var]["rel"], 0.05) / target)))
    for kv in (choice or "").split(","):
        if "=" in kv:
            k, v = kv.split("="); best[k.strip()] = v.strip()
    L = ["# «Кот Барсик», круг 2 — слова на стыке", "",
         "«Стык» — короткое неслужебное слово прямо перед ударным слогом следующего («кот Барсик», «наш кот», «брат купил»).",
         "«в слогах» — длина слова в средних слогах этой же записи (1,0 = как средний слог); «тон» — выше (+) или ниже (−) среднего тона",
         f"фразы, полутоны. Мерка — среднее по эталонам: **{target:.2f} слога**.", "",
         "| голос | вариант | слов | длина, с | в слогах | тон | громк., дБ | пауза после, с | полная гласная | услышано | слова | UTMOS | всего, с | выбран |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for vk in V:
        for var, s in S.get(vk, {}).items():
            L.append(f"| {vk} | {var} — {NAMES.get(var, var)} | {s['n']} | {s['wdur']} | {s['rel']} | {s['dst']} | {s['dI']} | {s['gap']} | "
                     f"{s['full']} | {s['heard']} | {s['match']} | {s['utmos']} | {s['dur']} | {'✓' if best.get(vk) == var else ''} |")
    L += ["", "## «кот» в «Жил на свете кот Барсик…» (03) и «Кот Барсик нашёл…» (05)", "",
          "| голос | вариант | фраза | длина, с | в слогах | тон | гласная | распознано |", "|---|---|---|---|---|---|---|---|"]
    for vk, d in D.items():
        for var, recs in d.items():
            for r in recs:
                if r["k"] in (3, 5):
                    for m in r["mono"]:
                        if m["w"] == "кот":
                            L.append(f"| {vk} | {var} | {r['k']:02d} | {m['wdur']} | {m['rel']} | {m.get('dst')} | {m.get('top', '—')} | {r['heard'][:44]} |")
    open("cast8/itog2.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump({"best": best, "target": target, "stat": S, "data": D}, open("cast8/kot2.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("\n".join(L))
    titles = {"V4": ("№4 — образец", "как понравился (не свободный)"), "F1": ("Свободный", "наша смесь, лицензия MIT"),
              "F2": ("Свободный", "наша смесь, лицензия MIT"), "F3": ("Свободный", "наша смесь, лицензия MIT")}
    pick = [(titles[vk][0], f"K2__{vk}{best[vk]}", titles[vk][1]) for vk in ("V4", "F1", "F2", "F3") if vk in best]
    svoy2.video(pick, "cast8/proba8.mp4", [(t, k < NL) for k, t in enumerate(PH)])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "tmp/all.wav", "-c:a", "libmp3lame", "-b:a", "160k", "cast8/proba8.mp3"], check=True)
    K1.check_file("cast8/proba8.mp4")


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2])
    else:
        final(sys.argv[2] if len(sys.argv) > 2 else None)
