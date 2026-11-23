#!/usr/bin/env python3
"""Голос №4: все омографы (23.11.2026, Михаил: «голос нравится, только надо все омографы, ударение правильно расставить»).

Ударение «+» ставим во ВСЕХ словах-омографах из словаря омографов ruaccent (а не в коротком списке), выбор ударения —
его же модель по смыслу фразы. Остальные слова модель v5_ru ставит сама.
Проверка — 30 фраз с частыми омографами, эталон ударений расставлен вручную, + 12 обычных фраз.
  A — №4 как было; E — №4 + все омографы; K — тот же текст, что E, голосом kseniya (контроль анализатора:
      если у неё «ошибка» там же — ошибается анализатор на низком голосе, а не голос).
  python svoy_omo.py gen <A|E|K> <part> <n>
  python svoy_omo.py final
"""
import glob, json, os, re, shutil, sys
import svoy, svoy2, svoy_bars

HOMO_TEST = [
    "На двери висел тяжёлый зам+ок, а за рекой стоял старый з+амок.",
    "Бабушка купила мешок мук+и, а ожидание обеда стало настоящей м+укой.",
    "Д+ома никого не было, и все дом+а на улице были тёмными.",
    "Сколько ст+оит этот дом, который сто+ит на горе?",
    "+Атлас лежал на столе, а платье было из атл+аса.",
    "В соборе играл старинный орг+ан, а сердце у человека самый важный +орган.",
    "Я плач+у за билет и пл+ачу от радости.",
    "Б+елки прыгали по веткам, а нам для роста нужны белк+и.",
    "Круг+ом лежал снег, и у меня голова шла кр+угом.",
    "Налей мне вод+ы, ведь подземные в+оды текут глубоко.",
    "Он помыл р+уки и попросил у отца её рук+и.",
    "С гор+ы бежал ручей, а высокие г+оры стояли в снегу.",
    "Из х+лопка делают ткань, а за окном раздался громкий хлоп+ок.",
    "Орёл может пар+ить в небе часами, а бабушка любит п+арить репу.",
    "В саду расцвёл синий +ирис, а дети любят сладкий ир+ис.",
    "Он боялся проп+асть в лесу, ведь внизу была глубокая пр+опасть.",
    "На стене висели п+олки, а по дороге шли полк+и солдат.",
    "На столе стояли кр+ужки с чаем, а дети ходят в разные кружк+и.",
    "У дедушки седые виск+и.",
    "Я уж+е д+ома, а эта дорога +уже той.",
    "На столе лежали маленькие гв+оздики, а в вазе стояли гвозд+ики.",
    "Стояло ж+аркое лето, а на обед было жарк+ое.",
    "Малыш начал засып+ать, а папа решил зас+ыпать яму песком.",
    "Я м+ою посуду, а ты возьми мо+ю чашку.",
    "На ветке сидела сор+ока, а в классе было с+орок учеников.",
    "Мама купила новые дух+и, а в сказке жили лесные д+ухи.",
    "Мы вышли из л+еса, а вокруг шумели лес+а.",
    "Лодка стояла у б+ерега, а берег+а реки были крутыми.",
    "Он не сказал ни сл+ова, но слов+а были не нужны.",
    "Он выглянул из окн+а, а все +окна были открыты.",
]
LISTEN = {0, 1, 2, 3, 5, 6, 8, 9, 19, 23, 24, 26, 28}
NAMES = {"A": "№4 как было", "E": "№4 + все омографы", "K": "контроль: kseniya, текст как у E"}
VOICE = {"A": svoy_bars.W4, "E": svoy_bars.W4, "K": {r: {"kseniya": 1.0} for r in ("dp", "pp", "spe")}}


def phrases():
    std = [t for k, t in enumerate(svoy_bars.phrases()) if k < 12 and "зам+ок" not in t]
    return HOMO_TEST + std


_acc = {}


def ruacc():
    if "a" not in _acc:
        try:
            import importlib
            RUAccent = importlib.import_module("ruaccent.ruaccent").RUAccent   # настоящий класс (svoy2.patch_ruaccent подменяет его в пакете)
        except Exception:
            from ruaccent import RUAccent
        a = RUAccent()
        for size in ["turbo3.1", "turbo3", "turbo2", "turbo", "tiny2", "tiny"]:
            try:
                a.load(omograph_model_size=size, use_dictionary=True); break
            except Exception:
                continue
        om = None
        for k, v in vars(a).items():           # словарь омографов: ищем по известным словам
            try:
                if isinstance(v, (dict, set, list, frozenset)) and "замок" in v and "атлас" in v and "мука" in v:
                    om = set(v) if not isinstance(v, dict) else set(v.keys()); svoy.log("омографы ruaccent:", k, len(om)); break
            except Exception:
                pass
        if om is None:
            svoy.log("словарь омографов не найден, атрибуты:", [(k, type(v).__name__, len(v) if hasattr(v, "__len__") else "") for k, v in vars(a).items()])
            om = svoy_bars.HOMO
        _acc["a"], _acc["om"] = a, {w.replace("+", "").lower() for w in om}
    return _acc["a"], _acc["om"]


def omo_marks(plain):
    """«+» во всех омографах по выбору ruaccent; возвращает текст и список (слово, номер ударной гласной)."""
    import voice_check as vc
    acc, om = ruacc()
    ws = vc.tokenize(plain)
    rw = vc.tokenize(acc.process_all(plain))
    if len(rw) != len(ws):
        svoy.log("ruaccent: слова не совпали", plain); rw = [{"exp": None}] * len(ws)
    toks = re.findall(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*|[^А-Яа-яЁё]+", plain)
    out, i, chosen = [], 0, []
    for tok in toks:
        if re.match(r"[А-Яа-яЁё]", tok):
            w, r = ws[i], rw[i]; i += 1
            if w["w"] in om and len(w["vows"]) > 1 and r["exp"] is not None:
                chosen.append((w["w"], r["exp"]))
                k = -1; t2 = ""
                for c in tok:
                    if c.lower() in vc.VOW:
                        k += 1
                        if k == r["exp"]:
                            t2 += "+"
                    t2 += c
                tok = t2
        out.append(tok)
    return "".join(out), chosen


def text_check():
    """Без звука: совпал ли выбор ruaccent с ручным эталоном в каждом омографе."""
    import voice_check as vc
    res = []
    for ref in HOMO_TEST:
        _, chosen = omo_marks(ref.replace("+", ""))
        got = dict()
        for w, e in chosen:
            got.setdefault(w, []).append(e)
        for w in vc.tokenize(ref):
            if "+" in w["raw"] and len(w["vows"]) > 1:
                e = got.get(w["w"], [None]).pop(0) if got.get(w["w"]) else None
                res.append({"phrase": ref, "word": w["w"], "need": w["exp"], "ruaccent": e,
                            "ok": e == w["exp"], "need_m": vc.mark(w["w"], w["exp"]),
                            "got_m": vc.mark(w["w"], e) if e is not None else "—"})
    return res


def gen(v, part, n):
    if v != "A":
        ruacc()                 # загрузить настоящий ruaccent до подмены
    svoy2.patch_ruaccent()
    shutil.rmtree("in", ignore_errors=True); shutil.rmtree("out", ignore_errors=True)
    os.makedirs("in"); os.makedirs("out"); os.makedirs("pack", exist_ok=True)
    net = svoy2.Net(svoy2.RU)
    rows = net.build(VOICE[v]); net.put(rows)
    sp = svoy2.SLOT[svoy2.RU]
    import gen as g
    P = phrases()
    for k in range(part, len(P), n):
        ref = P[k]; plain = ref.replace("+", "")
        text = plain if v == "A" else omo_marks(plain)[0]
        name = f"O__{v}__{k:02d}"
        a = net.m.apply_tts(text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
        g.save_wav(a.numpy() if hasattr(a, "numpy") else a, f"in/{name}.wav")
        open(f"in/{name}.txt", "w", encoding="utf-8").write(ref + "\n")
        open(f"in/{name}.voice", "w", encoding="utf-8").write(f"v5_ru {v}\n")
        open(f"in/{name}.sent", "w", encoding="utf-8").write(text + "\n")
        svoy.log(name, "|", text)
    if v == "E" and part == 0:
        tc = text_check()
        json.dump(tc, open("pack/textcheck.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        svoy.log("ruaccent по смыслу: верно", sum(r["ok"] for r in tc), "из", len(tc))
        for r in tc:
            if not r["ok"]:
                svoy.log("  ✗", r["phrase"], "|", r["need_m"], "→", r["got_m"])


def final():
    os.makedirs("cast5/png", exist_ok=True)
    R = svoy.load_reps()
    P = phrases()
    tc = json.load(open("pack/textcheck.json", encoding="utf-8")) if os.path.exists("pack/textcheck.json") else []
    L = ["# Голос №4 — все омографы", "",
         f"Словарь омографов ruaccent, выбор ударения по смыслу фразы: **верно {sum(r['ok'] for r in tc)} из {len(tc)}** "
         "(сверка текста с ручным эталоном, без звука).", ""]
    if tc:
        L += ["Где ruaccent выбрал не то:", ""] + [f"- «{r['phrase']}»: нужно {r['need_m']}, выбрал {r['got_m']}" for r in tc if not r["ok"]] + [""]
    L += ["| | вариант | слова | UTMOS | ошибки удар. (+возм.) | в омографах ✓/всего | интонация | темп |", "|---|---|---|---|---|---|---|---|"]
    hom = {}
    for v in "AEK":
        reps = R.get(f"O__{v}")
        if not reps:
            L.append(f"| {v} | {NAMES[v]} | нет данных |"); continue
        a = svoy.agg(reps)
        se = sum(r.get("stress_errors", 0) for r in reps); sm = sum(r.get("stress_maybe", 0) for r in reps)
        ok = tot = 0
        for r in reps:
            k = int(r["name"].rsplit("__", 1)[1])
            if k >= len(HOMO_TEST):
                continue
            refw = [w for w in svoy_vc().tokenize(P[k]) if "+" in w["raw"] and len(w["vows"]) > 1]
            names = {w["w"] for w in refw}
            for w in r.get("words", []):
                if w["w"] in names and w.get("exp") is not None:
                    tot += 1; ok += int(w.get("det") == w["exp"])
                    hom.setdefault((k, w["w"]), {})[v] = w.get("det") == w["exp"]
        L.append(f"| {v} | {NAMES[v]} | {a['match']:.3f} | {a['utmos']:.2f} | {se} (+{sm}) | {ok}/{tot} | {a['inton']:.2f} | {a['rate']:.1f} |")
    L += ["", "## Омографы по словам (анализатор по звуку; ✗ у E и ✓ у K → скорее ошибся анализатор на низком голосе)", "",
          "| фраза | слово | A | E | K |", "|---|---|---|---|---|"]
    m = lambda x: "—" if x is None else "✓" if x else "✗"
    for (k, w), d in sorted(hom.items()):
        L.append(f"| {k:02d} | {w} | {m(d.get('A'))} | {m(d.get('E'))} | {m(d.get('K'))} |")
    for p in glob.glob("pack/O__E__*.png"):
        shutil.copy(p, "cast5/png/")
    open("cast5/itog.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    svoy.log("\n".join(L))
    ph = [(t, k in LISTEN) for k, t in enumerate(P)]
    svoy2.video([(NAMES["E"], "O__E", "омографы с подсказкой ударений")], "cast5/proba5.mp4", ph)


def svoy_vc():
    import voice_check as vc
    return vc


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif sys.argv[1] == "tc":
        for r in text_check():
            print("✓" if r["ok"] else "✗", r["need_m"], r["got_m"], "|", r["phrase"])
    else:
        final()
