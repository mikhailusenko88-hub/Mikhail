#!/usr/bin/env python3
"""Чистая проба после замеров «кота» (24.11.2026). Что дали круги 1–2 (cast8/itog.md, itog2.md):
  • без «+» короткие слова у свободных голосов редуцируются («кат Барсик», «так течёт») — «+» обязателен;
  • на стыке («кот Барсик») короткое слово у ВСЕХ голосов Silero, включая Ксению, длится 0,7–0,9 среднего слога и склеивается
    со следующим; отдельный кусок SSML с темпом slow даёт 1,0–1,1 слога без потери естественности; x-slow — перебор («Коат-барсик»);
  • ускорение (rate=fast) у смесей g53 и g33 ломает слова («Туп кечет», «у жирах вот») — им темп medium; g03 fast выдерживает;
  • местоимения и указательные слова («ты видел», «наш кот», «вот этот») не вытягиваем — получается лишний нажим.
Вопрос без вопросительного слова — последнее слово slow + мелодия бота gen.qvrise (выбор Михаила 24.11).

Всё одним заданием: файлы не сливаются из разных заданий (в proba7 так испортился образец).
  python svoy_kot3.py     → cast8/proba8.mp4, cast8/proba8.mp3, cast8/itog3.md
"""
import json, os, re, subprocess
import numpy as np
import svoy, svoy2, svoy_bars, svoy_omo, svoy_free
import svoy_kot as K1, svoy_kot2 as K2

LISTEN_PH = K1.LISTEN_PH
TEST_PH = ["Кот Барсик нашёл в саду камень.", "Это наш кот, он любит спать.", "Ток течёт по проводам.", "Мой брат купил новый дом."]
PH = LISTEN_PH + TEST_PH
NL = len(LISTEN_PH)
PRON = set("""я ты он мы вы им их мой твой наш ваш свой тот та те вот вон там тут так как где кто чей сам весь все всё вся
был есть да нет раз лишь ведь""".split())
QWORDS = set("""почему зачем отчего кто что где куда откуда когда как какой какая какое какие каков сколько чей чья чьё чьи
который которая разве неужели""".split())
log = svoy.log


def configs():
    G = json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]
    a, b = G["ru_svoy1"], G["ru_svoy2"]
    return [
        {"id": "V4", "model": "ru", "w": svoy_bars.W4, "pitch": "medium", "rate": "medium",
         "title": "№4 — образец", "sub": "как понравился (не свободный)"},
        {"id": "A1", "model": "cis", "w": a["w"], "pitch": a["pitch"], "rate": "fast",
         "title": "Свободный, быстрый", "sub": "наша смесь, лицензия MIT"},
        {"id": "A2", "model": "cis", "w": a["w"], "pitch": a["pitch"], "rate": "medium",
         "title": "Свободный, спокойный", "sub": "тот же голос без ускорения"},
        {"id": "B2", "model": "cis", "w": b["w"], "pitch": b["pitch"], "rate": "medium",
         "title": "Свободный, другой тембр", "sub": "наша смесь, лицензия MIT"},
    ]


def yesno(plain):
    ws = re.findall(r"[А-Яа-яЁё]+", plain.lower())
    return plain.strip().endswith("?") and bool(ws) and not (set(ws[:3]) & QWORDS) and "ли" not in ws


def chunks(target, full, last_slow=False):
    """Куски SSML: (текст, медленно?). Медленно — короткое знаменательное слово на стыке (не местоимение) и, в вопросе без
    вопросительного слова, последнее слово."""
    tt, tf = K1.WORD.findall(target), K1.WORD.findall(full)
    if len(tt) != len(tf):
        return [(target, False)]
    words = [(i, t) for i, t in enumerate(tf) if K1.isword(t)]
    slow = set()
    for (i, t), (j, t2) in zip(words, words[1:]):
        w = t.replace("+", "").lower()
        if not K1.content_mono(t) or w in PRON or re.search(r"[.!?…,;:—–]", "".join(tf[i + 1:j])):
            continue
        k = t2.find("+")
        if (k >= 0 and K1.nv(t2[:k]) == 0) or (K1.content_mono(t2) and t2.replace("+", "").lower() not in PRON):
            slow.add(i)
    if last_slow and words:
        slow.add(words[-1][0])
    out, cur = [], ""
    for i, t in enumerate(tt):
        if i in slow:
            if cur.strip():
                out.append((cur, False)); cur = ""
            out.append((cur + t, True)); cur = ""
        else:
            cur += t
    if cur:
        out.append((cur, False))
    fixed = []                              # знаки и пробелы в начале куска («?», «, ») — в конец предыдущего
    for t, s_ in out:
        m = re.match(r"[^А-Яа-яЁё+]+", t)
        if m and fixed:
            lead = m.group(0)
            keep = lead[len(lead.rstrip()):] if lead.strip() else ""       # пробел перед следующим словом оставляем ему
            fixed[-1] = (fixed[-1][0] + lead[:len(lead) - len(keep)], fixed[-1][1])
            t = keep + t[len(lead):]
        if t.strip():
            fixed.append((t, s_))
        elif t and fixed:
            fixed[-1] = (fixed[-1][0] + t, fixed[-1][1])
    return fixed


def text_for(c, plain):
    full = svoy_free.mark_full(plain)
    target = K1.mono_plus(svoy_omo.omo_marks(plain)[0]) if c["model"] == "ru" else full
    return K2.chunks_ssml(chunks(target, full, last_slow=yesno(plain)), c["pitch"], c["rate"], "slow")


def last_syll(plain):
    ws = re.findall(r"[А-Яа-яЁё]+", plain)
    return K1.nv(ws[-1]) if ws else 1


def main():
    import gen as g
    for d in ("pack", "tmp", "cast8"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc()
    svoy2.patch_ruaccent()
    C = configs()
    net, rows = None, []
    L = ["# Чистая проба: №4 и свободные голоса, короткие слова вытянуты", "",
         "«в слогах» — длина короткого слова на стыке в средних слогах записи (было 0,7–0,9; цель около 1,0–1,2).", "",
         "| голос | темп | слова | UTMOS | длина 5 фраз, с | «кот» в «кот Барсик», с / в слогах | вопрос: конец выше середины, полутоны |",
         "|---|---|---|---|---|---|---|"]
    for c in C:
        mid = svoy2.RU if c["model"] == "ru" else svoy2.CIS
        if net is None or net.mid != mid:
            net = svoy2.Net(mid)
        net.put(net.build(c["w"]))
        sp = svoy2.SLOT[mid]
        recs, qst = [], None
        for k, plain in enumerate(PH):
            text = text_for(c, plain)
            p = f"tmp/P__{c['id']}__{k:02d}.wav"
            if c["model"] == "ru":
                try:
                    a = net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
                except TypeError:
                    a = net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000)
            else:
                a = net.m.apply_tts(ssml_text=text, speaker=sp, sample_rate=48000)
            g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
            if yesno(plain):
                try:
                    g.qvrise(p, win=min(0.48, 0.22 + 0.10 * last_syll(plain)))
                except Exception as e:
                    log("мелодия вопроса не легла:", c["id"], repr(e))
            r = K2.measure(p, plain); r["k"] = k; r["sent"] = text
            if yesno(plain):          # подъём в конце: высота последних 0,15 с против середины фразы
                import voice_check as vc
                _, pt, f0, _, _ = vc.prosody(vc.load16(p))
                v = f0 > 0
                if v.sum() > 10:
                    tend = pt[v][-1]
                    tail = f0[v & (pt >= tend - 0.15)]
                    qst = round(float(np.median([vc.st(x) for x in tail]) - np.median([vc.st(x) for x in f0[v]])), 1)
            recs.append(r)
            if k < NL:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/P__{c['id']}__{k:02d}.flac"], check=True)
            cl = [(m["w"], m["wdur"], m["rel"], m.get("top")) for m in r["mono"] if m["clash"]]
            log(f"{c['id']} {k:02d} UTMOS {r['utmos']} слова {r['match']} {r['dur']} с | {r['heard']} | стык: {cl} | {re.sub('<[^>]+>', '|', text)[:110]}")
        lis = recs[:NL]
        kot = [m for r in recs if r["k"] in (3, NL) for m in r["mono"] if m["w"] == "кот"]
        L.append(f"| {c['id']} — {c['title']} | {c['rate']} | {np.mean([r['match'] for r in lis]):.3f} | {np.mean([r['utmos'] for r in lis]):.2f} | "
                 f"{sum(r['dur'] for r in lis):.1f} | {'; '.join(str(m['wdur']) + ' / ' + str(m['rel']) for m in kot)} | {qst} |")
        rows.append({"id": c["id"], "recs": recs})
    L += ["", "## Что распознал распознаватель слов (где не совпало)", ""]
    for row in rows:
        for r in row["recs"]:
            if r["match"] < 0.95:
                L.append(f"- {row['id']} {r['k']:02d}: «{PH[r['k']]}» → «{r['heard']}»")
    open("cast8/itog3.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(rows, open("cast8/kot3.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("\n".join(L))
    pick = [(c["title"], f"P__{c['id']}", c["sub"]) for c in C]
    svoy2.video(pick, "cast8/proba8.mp4", [(t, k < NL) for k, t in enumerate(PH)])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "tmp/all.wav", "-c:a", "libmp3lame", "-b:a", "160k", "cast8/proba8.mp3"], check=True)
    K1.check_file("cast8/proba8.mp4")


if __name__ == "__main__":
    main()
