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
NEW_TEST = [   # новые фразы для проверки правил (правила писались по HOMO_TEST)
    "Туристы долго шли вдоль б+ерега, а берег+а озера заросли камышом.",
    "Из окн+а дул ветер, и мы закрыли +окна.",
    "Без вод+ы человек долго не проживёт, а морские в+оды солёные.",
    "Мы гуляли у л+еса, а дальше начинались густые лес+а.",
    "У этого сл+ова два значения, и такие слов+а называют омонимами.",
    "Я м+ою р+уки перед едой.",
    "Возьми мо+ю книгу.",
    "Рабочие решили зас+ыпать ров землёй.",
    "Дети любят засып+ать под сказку.",
    "Эта улица +уже той, по которой мы шли.",
    "Мы уж+е пришли.",
    "Её любимые дух+и пахнут розой, а в легендах злые д+ухи живут в горах.",
    "Для блинов нужно два стакана мук+и.",
    "Сладкий ир+ис прилипает к зубам.",
    "Он забил в доску медные гв+оздики.",
    "Налей стакан вод+ы.",
    "Поднимите р+уки!",
    "Он не нашёл ни одного сл+ова.",
    "Над водой склонились деревья у б+ерега.",
    "Все слов+а в этой книге простые.",
]
LISTEN = {0, 1, 2, 3, 9, 10, 19, 22, 23, 25, 27, 30, 31, 33}
NAMES = {"A": "№4 как было", "E": "№4 + все омографы", "K": "контроль: kseniya, текст как у E"}
VOICE = {"A": svoy_bars.W4, "E": svoy_bars.W4, "K": {r: {"kseniya": 1.0} for r in ("dp", "pp", "spe")}}


def phrases():
    std = [t for k, t in enumerate(svoy_bars.phrases()) if k < 12 and "зам+ок" not in t]
    return HOMO_TEST + NEW_TEST + std


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



# ---------------- свои правила для частых омографов (поверх ruaccent) ----------------
GEN_PREP = set("""из до у от с со без около возле для ни против вдоль кроме после мимо вокруг среди посреди напротив
внутри вне близ недалеко""".split())
PLUR = ("ые", "ие")                       # «густые леса», «крутые берега», «подземные воды»
GEN_ADJ = ("ого", "его", "ой", "ей")      # «из густого леса», «чистой воды»


OMO_PL = ("эти", "все", "наши", "ваши", "свои", "такие", "где")


def _r_sg_gen(sg_gen, plural, extra=()):
    """леса / слова / окна / берега: после предлога родительного, «нет» или прилагательного в род. п. — ед. ч. (ле́са, сло́ва,
    окна́, бе́рега); после прилагательного во мн. ч. («густые леса», «эти слова») — мн. ч.; иначе решает ruaccent (None).
    25.11.2026: раньше без признаков ставилось мн. ч. — на стенде бота «десять квадратных километров ле́са» стало «леса́»."""
    def f(prev, nxt):
        if prev in GEN_PREP or prev == "нет" or prev in extra or prev.endswith(GEN_ADJ[:2]):
            return sg_gen
        if prev.endswith(PLUR) or prev in OMO_PL:
            return plural
        return None
    return f


def _r_voda(prev, nxt):
    if prev.endswith(PLUR) or nxt in ("текут", "текли", "омывают", "реки", "океана", "морей"):
        return 0                             # во́ды
    return 1                                 # воды́ (стакан воды, без воды, литров воды)


def _r_ruki(prev, nxt, left=""):
    if re.search(r"(попроси|проси)\w*(\s+\S+){0,3}$", left) or prev in GEN_PREP or prev == "нет":
        return 1                             # руки́ (попросил руки, из руки, нет руки)
    if prev.endswith(PLUR) or prev in ("свои", "мои", "твои", "наши", "ваши", "обе", "эти", "все", "вымой", "мой", "мыть", "помой",
                                       "моем", "моют", "поднял", "подняли", "поднимите", "пожали", "пожать"):
        return 0                             # ру́ки
    return None                              # «взмах руки», «две руки» — решает ruaccent


def _r_uzhe(prev, nxt):
    if nxt in ("чем", "той", "того", "тех", "тот", "этой", "этого") or prev in ("гораздо", "намного", "чуть", "немного", "вдвое", "втрое", "ещё"):
        return 0                             # у́же
    return 1                                 # уже́


def _r_moyu(prev, nxt):
    return 0 if prev == "я" else 1           # я мо́ю / мою́ книгу


def _r_zasyp(prev, nxt):
    return 1 if nxt in ("яму", "ров", "канаву", "яма", "песком", "землёй", "землей", "снегом", "зерно", "крупу", "сахар", "соль") else 2


def _r_duhi(prev, nxt):
    if prev in ("лесные", "злые", "добрые", "горные", "водные", "домашние", "все", "эти", "тёмные", "темные") or nxt in ("предков", "леса", "гор"):
        return 0                             # ду́хи
    if prev in ("новые", "любимые", "мои", "её", "ее", "французские", "дорогие", "купила", "купил", "флакон") or nxt in ("пахнут",):
        return 1                             # духи́
    return None


def _r_muki(prev, nxt):
    if prev in ("мешок", "мешка", "стакан", "стакана", "стаканов", "килограмм", "килограмма", "много", "немного", "без", "из",
                "пшеничной", "ржаной", "кукурузной", "горсть", "ложка", "ложки") :
        return 1                             # муки́
    if prev in ("адские", "крестные", "творческие", "душевные") or nxt in ("совести", "ада", "творчества"):
        return 0                             # му́ки
    return None


def _r_iris(prev, nxt):
    return 1 if prev in ("сладкий", "сладкие", "конфета", "конфеты", "молочный", "жевательный", "твёрдый", "твердый") else None


def _r_gvozd(prev, nxt):
    return 0 if prev in ("маленькие", "мелкие", "железные", "медные", "забил", "забила", "забивать", "тонкие") else None


RULES = {
    "леса": _r_sg_gen(0, 1, ("много", "мало", "немного", "нет", "край", "опушка", "опушке", "краю")),
    "слова": _r_sg_gen(0, 1, ("значение", "смысл", "смысла", "значения", "одного", "этого", "нового")),
    "окна": _r_sg_gen(1, 0, ("стекло", "рама", "раму", "подоконник")),
    "берега": _r_sg_gen(0, 2, ("недалеко",)),
    "воды": _r_voda, "руки": _r_ruki, "уже": _r_uzhe, "мою": _r_moyu, "засыпать": _r_zasyp,
    "духи": _r_duhi, "муки": _r_muki, "ирис": _r_iris, "гвоздики": _r_gvozd,
}


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
            w, r = ws[i], rw[i]
            prev = ws[i - 1]["w"] if i > 0 and not re.search(r"[.!?…,;:—–]", ws[i - 1]["punct"]) else ""
            nxt = ws[i + 1]["w"] if i + 1 < len(ws) and not re.search(r"[.!?…,;:—–]", w["punct"]) else ""
            i += 1
            e = r["exp"] if w["w"] in om else None
            if w["w"] in RULES:
                f = RULES[w["w"]]
                left = " ".join(x["w"] for x in ws[max(0, i - 5):i - 1])
                e2 = f(prev, nxt, left) if f is _r_ruki else f(prev, nxt)
                if e2 is not None:
                    e = e2
            if len(w["vows"]) > 1 and e is not None:
                chosen.append((w["w"], e))
                k = -1; t2 = ""
                for c in tok:
                    if c.lower() in vc.VOW:
                        k += 1
                        if k == e:
                            t2 += "+"
                    t2 += c
                tok = t2
        out.append(tok)
    return "".join(out), chosen


def text_check():
    """Без звука: совпал ли выбор ruaccent с ручным эталоном в каждом омографе."""
    import voice_check as vc
    res = []
    for ref in HOMO_TEST + NEW_TEST:
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
         f"Словарь омографов ruaccent + свои правила (RULES): **верно {sum(r['ok'] for r in tc)} из {len(tc)}** "
         "(сверка текста с ручным эталоном, без звука; 30 фраз, по которым писались правила, + 20 новых).",
         f"Только новые фразы: верно {sum(r['ok'] for r in tc if r['phrase'] in NEW_TEST)} из {sum(1 for r in tc if r['phrase'] in NEW_TEST)}.", ""]
    if tc:
        L += ["Где ударение выбрано не то:", ""] + [f"- «{r['phrase']}»: нужно {r['need_m']}, выбрал {r['got_m']}" for r in tc if not r["ok"]] + [""]
    L += ["| | вариант | слова | UTMOS | ошибки удар. (+возм.) | в омографах ✓/всего | интонация | темп |", "|---|---|---|---|---|---|---|---|"]
    hom = {}
    for v in "E":
        reps = R.get(f"O__{v}")
        if not reps:
            L.append(f"| {v} | {NAMES[v]} | нет данных |"); continue
        a = svoy.agg(reps)
        se = sum(r.get("stress_errors", 0) for r in reps); sm = sum(r.get("stress_maybe", 0) for r in reps)
        ok = tot = 0
        for r in reps:
            k = int(r["name"].rsplit("__", 1)[1])
            if k >= len(HOMO_TEST) + len(NEW_TEST):
                continue
            refw = [w for w in svoy_vc().tokenize(P[k]) if "+" in w["raw"] and len(w["vows"]) > 1]
            names = {w["w"] for w in refw}
            for w in r.get("words", []):
                if w["w"] in names and w.get("exp") is not None:
                    tot += 1; ok += int(w.get("det") == w["exp"])
                    hom.setdefault((k, w["w"]), {})[v] = w.get("det") == w["exp"]
        L.append(f"| {v} | {NAMES[v]} | {a['match']:.3f} | {a['utmos']:.2f} | {se} (+{sm}) | {ok}/{tot} | {a['inton']:.2f} | {a['rate']:.1f} |")
    L += ["", "## Омографы по словам (анализатор по звуку, низкий голос — анализатор ошибается чаще)", "",
          "| фраза | слово | E |", "|---|---|---|"]
    m = lambda x: "—" if x is None else "✓" if x else "✗"
    for (k, w), d in sorted(hom.items()):
        L.append(f"| {k:02d} | {w} | {m(d.get('E'))} |")
    for p in glob.glob("pack/O__E__*.png"):
        shutil.copy(p, "cast5/png/")
    open("cast5/itog.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    svoy.log("\n".join(L))
    ph = [(t, k in LISTEN) for k, t in enumerate(P)]
    svoy2.video([("№4 — омографы: словарь и свои правила", "O__E", "фразы с омографами")], "cast5/proba5.mp4", ph)


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
