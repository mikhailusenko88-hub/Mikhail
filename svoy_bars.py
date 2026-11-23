#!/usr/bin/env python3
"""Голос №4 (23.11.2026, Михаил: «просто восторг», доработать «шикарно»): манера Барсика мужским голосом —
модель Silero v5_ru, ритм xenia, мелодия 70% xenia + 30% eugene, тембр eugene (q00 из круга 2).
Ошибка, которую услышал Михаил: «замок» и «замок» в одной фразе прочитаны одинаково.

Варианты (голос тот же):
  A — как было (модель сама ставит ударения);
  B — то же + ударения «+» в словах-омографах (замок, мука, дома, стоит, атлас…) по словарю ruaccent;
  C — B и чуть спокойнее (темп ×0,94, высота та же): у №4 темп 6,7 слога/с, слова слипаются («горбу не» → «горбоне»);
  D — ударения «+» во всех словах по ruaccent (проверка, не лучше ли размечать всё).
  python svoy_bars.py gen <A|B|C|D>   озвучка в in/ для voice_check.py
  python svoy_bars.py final           cast4/itog.md, cast4/proba4.mp4
"""
import glob, json, os, re, shutil, subprocess, sys
import svoy, svoy2

W4 = {"dp": {"xenia": 1.0}, "pp": {"xenia": 0.7, "eugene": 0.3}, "spe": {"eugene": 1.0}}
# фразы-омографы: эталон с ударениями, проставленными вручную (их проверяет анализатор, а не тот же словарь)
HOMO_PH = [
    "На двери висел тяжёлый зам+ок, а за рекой стоял старый з+амок.",
    "Он пёк хлеб из мук+и и знал, что такое м+ука.",
    "Д+ома никого не было, и все дом+а на улице были тёмными.",
    "Сколько ст+оит этот дом, который сто+ит на горе?",
    "+Атлас лежал на столе, а платье было из атл+аса.",
]
HOMO = set("""замок замка замку замком замке замки замков мука муки муку мукой дома стоит стоят атлас атласа атласе
белки кругом уже хлопок ирис орган парить плачу пропасть сорок полки руки воды горы кружки жаркое виски мою
трусы гвоздики засыпать насыпать выходит""".split())
LISTEN = {0, 5, 10, 12, 13, 14, 15}        # слушать: жираф, «Ты видел снег…?», пять фраз-омографов
TEMPO_C = 0.94
NAMES = {"A": "№4 как было", "B": "№4 + ударения в омографах", "C": "№4 + омографы, чуть спокойнее",
         "D": "№4 + ударения во всех словах"}


def phrases():
    P = []
    for t, _ in svoy2.PHRASES:
        if "замок" in t:
            t = HOMO_PH[0]          # та же фраза, эталон с ручными ударениями
        P.append(t)
    P += HOMO_PH[1:]
    return P


def homo_marks(plain):
    """«+» только в омографах — по словарю ruaccent (как будет в боте); остальное модель ставит сама."""
    import voice_check as vc
    ws = vc.tokenize(plain)
    vc.accentize(plain, ws)
    words = re.findall(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*|[^А-Яа-яЁё]+", plain)
    out, i = [], 0
    for tok in words:
        if re.match(r"[А-Яа-яЁё]", tok):
            w = ws[i]; i += 1
            if w["w"] in HOMO and w["exp"] is not None and len(w["vows"]) > 1:
                k = -1; t2 = ""
                for c in tok:
                    if c.lower() in vc.VOW:
                        k += 1
                        if k == w["exp"]:
                            t2 += "+"
                    t2 += c
                tok = t2
        out.append(tok)
    return "".join(out)


def gen(v):
    svoy2.patch_ruaccent()
    shutil.rmtree("in", ignore_errors=True); shutil.rmtree("out", ignore_errors=True)
    os.makedirs("in"); os.makedirs("out")
    net = svoy2.Net(svoy2.RU)
    rows = net.build(W4)
    net.put(rows)
    sp = svoy2.SLOT[svoy2.RU]
    import gen as g
    for k, ref in enumerate(phrases()):
        plain = ref.replace("+", "")
        text = plain if v == "A" else homo_marks(plain) if v in "BC" else svoy.mark(plain)
        name = f"V__{v}__{k:02d}"
        a = net.m.apply_tts(text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
        g.save_wav(a.numpy() if hasattr(a, "numpy") else a, f"in/{name}.wav")
        if v == "C":
            tmp = f"in/{name}.t.wav"
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"in/{name}.wav", "-af", f"rubberband=tempo={TEMPO_C}",
                                tmp])
            if r.returncode != 0:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"in/{name}.wav", "-af", f"atempo={TEMPO_C}", tmp], check=True)
            os.replace(tmp, f"in/{name}.wav")
        open(f"in/{name}.txt", "w", encoding="utf-8").write(ref + "\n")
        open(f"in/{name}.voice", "w", encoding="utf-8").write(f"v5_ru №4 {v}\n")
        svoy.log(name, "|", text)


def final():
    os.makedirs("cast4", exist_ok=True)
    R = svoy.load_reps()
    P = phrases()
    L = ["# Голос №4 (манера Барсика, мужской) — доработка", "",
         "Состав: модель Silero v5_ru, ритм xenia, мелодия 70% xenia + 30% eugene, тембр eugene.",
         "Эталон ударений в омографах проставлен вручную; остальное — словарь анализатора.", "",
         "| | вариант | слова | UTMOS | ошибки удар. (+возм.) | интонация | диапазон | Гц | темп | оценка |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for v in "ABCD":
        reps = R.get(f"V__{v}")
        if not reps:
            L.append(f"| {v} | {NAMES[v]} | нет данных |"); continue
        a = svoy.agg(reps)
        se = sum(r.get("stress_errors", 0) for r in reps); sm = sum(r.get("stress_maybe", 0) for r in reps)
        L.append(f"| {v} | {NAMES[v]} | {a['match']:.3f} | {a['utmos']:.2f} | {se} (+{sm}) | {a['inton']:.2f} | "
                 f"{a['range']:.1f} | {a['f0']:.0f} | {a['rate']:.1f} | {svoy.score(a)} |")
        detail += ["", f"## {v} — {NAMES[v]}", ""]
        for r in sorted(reps, key=lambda r: r["name"]):
            k = int(r["name"].rsplit("__", 1)[1])
            badw = [w["w"] for w in r.get("words", []) if w.get("exp") is not None and w.get("det") is not None
                    and w["exp"] != w["det"] and (w.get("margin") or 0) >= 0.5]
            homo = [(w["w"], "✓" if w.get("det") == w.get("exp") else "✗" if w.get("det") is not None else "?")
                    for w in r.get("words", []) if w["w"] in HOMO]
            if r.get("diff") or badw or any(h[1] != "✓" for h in homo):
                detail.append(f"- {k:02d} «{P[k]}» → слышно «{r.get('heard', '')}»; ударение не там: {', '.join(badw) or '—'}; "
                              f"омографы: {' '.join(f'{w}{s}' for w, s in homo) or '—'}")
    os.makedirs("cast4/png", exist_ok=True)
    for p in glob.glob("pack/V__*.png"):
        shutil.copy(p, "cast4/png/")
    open("cast4/itog.md", "w", encoding="utf-8").write("\n".join(L + detail) + "\n")
    svoy.log("\n".join(L + detail))
    ph = [(t, k in LISTEN) for k, t in enumerate(P)]
    pick = []
    for v in "ABCD":
        reps = R.get(f"V__{v}")
        sub = " "
        if reps:
            a = svoy.agg(reps)
            se = sum(r.get("stress_errors", 0) for r in reps)
            sub = f"ударений мимо {se}, естественность {a['utmos']:.2f}"
        pick.append((NAMES[v], f"V__{v}", sub))
    svoy2.video(pick, "cast4/proba4.mp4", ph)


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2])
    else:
        final()
