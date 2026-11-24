#!/usr/bin/env python3
"""«Кот Барсик» — короткие слова (24.11.2026). Михаил: «поработай над ударением: „кот Барсик“ — „кот“ плохо почти все говорят».
И чистая пересборка пробы: в proba7 записи образца №4 повредились (16 заданий писали файлы T4__NN.flac с одним именем,
download-artifact сливал их параллельно → «invalid sync code» у flac, из фраз выпали куски).

Голоса: V4 — №4 (модель Барсика v5_ru, только образец), F1–F3 — свободные (v5_cis, MIT) из cast7/golos_free.json.
Варианты разметки коротких (односложных неслужебных) слов:
  V4:  a — как было (ударение ставит сама модель);  b — «+» в коротких словах («к+от»)
  F*:  a — как было («+» в коротких словах);  b — без «+» в коротких (для сравнения);
       c — a + короткое слово перед ударным слогом читается отдельным куском медленнее;  d — a без ускорения (для сравнения)
Замер: что услышал распознаватель слов, какую гласную услышал фонемный распознаватель (полная «о» или редуцированная «а»),
форманты гласной (Praat), длина слова, естественность (UTMOS).
  python svoy_kot.py gen <V4|F1|F2|F3>    озвучка + замер → pack/
  python svoy_kot.py final                 cast8/itog.md, cast8/proba8.mp4, cast8/proba8.mp3
"""
import difflib, glob, json, os, re, subprocess, sys
import numpy as np
import svoy, svoy2, svoy_bars, svoy_omo, svoy_free

LISTEN_PH = [svoy2.PHRASES[k][0] for k in (0, 2, 5, 6, 10)]
TEST_PH = [
    "Кот Барсик нашёл в саду камень.",
    "Это наш кот, он любит спать.",
    "Мой брат купил новый дом.",
    "Ток течёт по проводам.",
    "Снег лёг на дом и сад.",
    "Он шёл в лес пять дней.",
    "Кит плывёт на юг.",
    "Вот этот дом стоит сто лет.",
]
PH = LISTEN_PH + TEST_PH          # 0–4 — в ролик, 5–12 — проверка коротких слов
VOW = "аеёиоуыэюя"
WORD = re.compile(r"[А-Яа-яЁё+]+(?:-[А-Яа-яЁё+]+)*|[^А-Яа-яЁё+]+")
STEP = {"fast": "medium", "medium": "slow", "slow": "x-slow"}
NAMES = {"a": "как было", "b": "V4: «+» в коротких словах / F: без «+» в коротких", "c": "короткое слово отдельным куском, медленнее",
         "d": "без ускорения"}
log = svoy.log


def voices():
    G = json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]
    V = {"V4": {"model": "ru", "w": svoy_bars.W4, "vars": "ab"}}
    for i in (1, 2, 3):
        g = G[f"ru_svoy{i}"]
        V[f"F{i}"] = {"model": "cis", "w": g["w"], "pitch": g["pitch"], "srate": g["rate_ssml"], "vars": "abcd"}
    return V


def isword(t):
    return bool(re.match(r"[А-Яа-яЁё+]", t))


def nv(w):
    return sum(1 for c in w.lower() if c in VOW)


def content_mono(t):
    return nv(t) == 1 and t.replace("+", "").lower() not in svoy.CLIT


def mono_plus(marked):
    """«+» в односложные неслужебные слова, где его ещё нет: кот → к+от."""
    out = []
    for tok in WORD.findall(marked):
        if isword(tok) and "+" not in tok and content_mono(tok):
            i = next(j for j, c in enumerate(tok) if c.lower() in VOW)
            tok = tok[:i] + "+" + tok[i:]
        out.append(tok)
    return "".join(out)


def mono_strip(marked):
    return "".join(tok.replace("+", "") if isword(tok) and nv(tok) == 1 else tok for tok in WORD.findall(marked))


def clash_chunks(marked):
    """Куски для SSML: короткое неслужебное слово прямо перед ударным слогом следующего слова («к+от Б+арсик», «н+аш к+от») —
    отдельным куском, на ступень медленнее."""
    toks = WORD.findall(marked)
    words = [(i, t) for i, t in enumerate(toks) if isword(t)]
    slow = set()
    for (i, t), (j, t2) in zip(words, words[1:]):
        if not content_mono(t) or re.search(r"[.!?…,;:—–]", "".join(toks[i + 1:j])):
            continue
        k = t2.find("+")
        if (k >= 0 and nv(t2[:k]) == 0) or content_mono(t2):
            slow.add(i)
    chunks, cur = [], ""
    for i, t in enumerate(toks):
        if i in slow:
            if cur:
                chunks.append((cur, False)); cur = ""
            chunks.append((t, True))
        else:
            cur += t
    if cur:
        chunks.append((cur, False))
    return chunks


def ssml(x, pitch, rate):
    if isinstance(x, str):
        return f'<speak><prosody rate="{rate}" pitch="{pitch}">{x}</prosody></speak>'
    return "<speak>" + "".join(f'<prosody rate="{STEP[rate] if s else rate}" pitch="{pitch}">{t}</prosody>' for t, s in x) + "</speak>"


def text_for(v, var, plain):
    if v["model"] == "ru":
        base = svoy_omo.omo_marks(plain)[0]
        return base if var == "a" else mono_plus(base)
    full = svoy_free.mark_full(plain)
    if var == "a":
        return ssml(full, v["pitch"], v["srate"])
    if var == "b":
        return ssml(mono_strip(full), v["pitch"], v["srate"])
    if var == "c":
        return ssml(clash_chunks(full), v["pitch"], v["srate"])
    return ssml(full, v["pitch"], "medium")


def measure(path, plain):
    import torch, parselmouth, voice_check as vc
    a = vc.load16(path)
    with torch.no_grad():
        ut = float(vc.utmos_model()(torch.from_numpy(a)[None], vc.SR))
    heard = vc.whisper_model().transcribe(path, language="ru", fp16=False)["text"]
    ref, hw = vc.norm_words(plain), vc.norm_words(heard)
    sm = difflib.SequenceMatcher(None, ref, hw)
    ok = set()
    for blk in sm.get_matching_blocks():
        ok.update(range(blk.a, blk.a + blk.size))
    words = vc.tokenize(plain)
    vowels = vc.align(a, words)
    fm = parselmouth.Sound(path).to_formant_burg(time_step=0.005, max_number_of_formants=5, maximum_formant=5000)
    rows = []
    for wi, w in enumerate(words):
        if len(w["vows"]) != 1 or w["w"] in svoy.CLIT:
            continue
        r = {"w": w["w"], "L": w["vows"][0], "heard_ok": wi in ok, "wdur": round(w.get("t1", 0) - w.get("t0", 0), 3)}
        v = next((x for x in vowels if x["w"] == wi), None)
        if v:
            pt = v["pt"]
            if r["L"] in vc.QSETS:
                full, red = vc.QSETS[r["L"]]
                r["full"] = round(sum(p for t, p in pt.items() if t in full), 3)
                r["red"] = round(sum(p for t, p in pt.items() if t in red), 3)
            r["top"] = v["ph"]
            for n in (1, 2):
                f = fm.get_value_at_time(n, v["c"])
                r[f"F{n}"] = None if f != f else int(round(f))
        rows.append(r)
    return {"utmos": round(ut, 3), "heard": heard.strip(), "match": round(sm.ratio(), 3), "dur": round(len(a) / vc.SR, 2), "mono": rows}


def gen(vk):
    import gen as g
    os.makedirs("pack", exist_ok=True); os.makedirs("tmp", exist_ok=True)
    v = voices()[vk]
    svoy_omo.ruacc()               # настоящий ruaccent — до подмены
    svoy2.patch_ruaccent()
    net = svoy2.Net(svoy2.RU if v["model"] == "ru" else svoy2.CIS)
    net.put(net.build(v["w"]))
    sp = svoy2.SLOT[net.mid]
    res = {}
    for var in v["vars"]:
        recs = []
        try:
            for k, plain in enumerate(PH):
                text = text_for(v, var, plain)
                p = f"tmp/K__{vk}{var}__{k:02d}.wav"
                if v["model"] == "ru":
                    a = net.m.apply_tts(text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
                else:
                    a = net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000)
                g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
                r = measure(p, plain); r["sent"] = text; r["k"] = k
                recs.append(r)
                if k < len(LISTEN_PH):
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/K__{vk}{var}__{k:02d}.flac"], check=True)
                kot = [m for m in r["mono"] if m["w"] == "кот"]
                log(f"{vk}{var} {k:02d} UTMOS {r['utmos']} слова {r['match']} | {r['heard']}" + (f" | кот: {kot}" if kot else ""))
            res[var] = recs
        except Exception as e:
            import traceback
            log("ОШИБКА", vk, var, repr(e)); traceback.print_exc()
    json.dump(res, open(f"pack/K_{vk}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def vscore(recs):
    mono = [m for r in recs for m in r["mono"]]

    def okm(m):
        return 0.5 * m["heard_ok"] + 0.5 * ((m["full"] > m["red"]) if "full" in m else m["heard_ok"])
    oo = [m for m in mono if m["L"] == "о" and "full" in m]
    s = {"mono_ok": round(float(np.mean([okm(m) for m in mono])), 3) if mono else 0,
         "o_full": round(float(np.mean([m["full"] > m["red"] for m in oo])), 3) if oo else None,
         "heard": round(float(np.mean([m["heard_ok"] for m in mono])), 3) if mono else 0,
         "match": round(float(np.mean([r["match"] for r in recs])), 3),
         "utmos": round(float(np.mean([r["utmos"] for r in recs])), 3),
         "dur": round(float(sum(r["dur"] for r in recs)), 1)}
    s["score"] = round(3 * s["mono_ok"] + s["match"] + 0.5 * s["utmos"], 3)
    return s


def choose(S):
    """Лучший вариант голоса. d (без ускорения) — только для сравнения. c — если не испортил естественность и не растянул речь."""
    cand = {k: s for k, s in S.items() if k in "abc"}
    if "c" in cand and "a" in S and (S["c"]["utmos"] < S["a"]["utmos"] - 0.05 or S["c"]["dur"] > 1.08 * S["a"]["dur"]):
        cand.pop("c")
    return max(cand, key=lambda k: cand[k]["score"])


def final():
    os.makedirs("cast8", exist_ok=True)
    V = voices()
    L = ["# «Кот Барсик» — короткие слова, и чистая проба", "",
         "Короткое слово = односложное неслужебное (кот, дом, он, наш, пять…). «полная о» — доля слов с буквой «о», где фонемный",
         "распознаватель услышал «о», а не «а»; «услышано» — доля коротких слов, которые распознаватель слов записал верно.",
         "Оценка = 3·(короткие слова в порядке) + совпадение слов + 0,5·UTMOS.", "",
         "| голос | вариант | короткие в порядке | полная «о» | услышано | слова | UTMOS | длина, с | оценка | выбран |", "|---|---|---|---|---|---|---|---|---|---|"]
    best, D = {}, {}
    for vk in V:
        f = f"pack/K_{vk}.json"
        if not os.path.exists(f):
            L.append(f"| {vk} | нет данных |"); continue
        D[vk] = json.load(open(f, encoding="utf-8"))
        S = {var: vscore(recs) for var, recs in D[vk].items() if recs}
        best[vk] = choose(S)
        for var, s in S.items():
            L.append(f"| {vk} | {var} — {NAMES[var]} | {s['mono_ok']} | {s['o_full']} | {s['heard']} | {s['match']} | {s['utmos']} | "
                     f"{s['dur']} | {s['score']} | {'✓' if var == best[vk] else ''} |")
    L += ["", "## Слово «кот» по вариантам (фразы «Жил на свете кот Барсик…», «Кот Барсик нашёл…», «Это наш кот…»)", "",
          "| голос | вариант | фраза | гласная | полная / редуц. | F1 / F2, Гц | длина слова, с | распознаватель слов |", "|---|---|---|---|---|---|---|---|"]
    for vk, d in D.items():
        for var, recs in d.items():
            for r in recs:
                for m in r["mono"]:
                    if m["w"] == "кот":
                        L.append(f"| {vk} | {var} | {r['k']:02d} | {m.get('top', '—')} | {m.get('full', '—')} / {m.get('red', '—')} | "
                                 f"{m.get('F1', '—')} / {m.get('F2', '—')} | {m['wdur']} | {'✓' if m['heard_ok'] else '✗ ' + r['heard'][:60]} |")
    L += ["", "## Все короткие слова выбранных вариантов, где что-то не так", ""]
    for vk, d in D.items():
        for r in d.get(best.get(vk), []):
            for m in r["mono"]:
                bad = (not m["heard_ok"]) or ("full" in m and m["full"] <= m["red"])
                if bad:
                    L.append(f"- {vk}{best[vk]} {r['k']:02d} «{m['w']}»: гласная {m.get('top', '—')} ({m.get('full', '—')}/{m.get('red', '—')}), "
                             f"распознано: «{r['heard'][:70]}» | отправлено: {re.sub('<[^>]+>', '', r['sent'])[:70]}")
    open("cast8/itog.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump({"best": best, "data": D}, open("cast8/kot.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("\n".join(L))
    titles = {"V4": ("№4 — образец", "как понравился (не свободный)"), "F1": ("Свободный", "наша смесь, лицензия MIT"),
              "F2": ("Свободный", "наша смесь, лицензия MIT"), "F3": ("Свободный", "наша смесь, лицензия MIT")}
    pick = [(titles[vk][0], f"K__{vk}{best[vk]}", titles[vk][1]) for vk in V if vk in best]
    ph = [(t, k < len(LISTEN_PH)) for k, t in enumerate(PH)]
    svoy2.video(pick, "cast8/proba8.mp4", ph)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "tmp/all.wav", "-c:a", "libmp3lame", "-b:a", "160k", "cast8/proba8.mp3"], check=True)
    check_file("cast8/proba8.mp4")


def check_file(path):
    """Ролик перед отправкой: звук без скачков времени, видео и звук одной длины."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "packet=pts_time", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.split()
    pts = [float(x.split(",")[0]) for x in out if x and not x.startswith("N/A")]
    jumps = sum(1 for i in range(len(pts) - 1) if abs(pts[i + 1] - pts[i] - 1024 / 48000) > 0.001)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True).stdout.split()
    log("проверка ролика:", path, "скачков времени в звуке:", jumps, "длины дорожек:", d)
    if jumps or (len(d) == 2 and abs(float(d[0]) - float(d[1])) > 0.1):
        raise RuntimeError("ролик собран с дефектом — не отправлять")


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2])
    elif sys.argv[1] == "final":
        final()
