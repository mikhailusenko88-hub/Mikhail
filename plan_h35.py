"""H35 (20.11.2026, «да» Михаила): слот 09:00 МСК — карточка-список «5 мыслей» вместо трёх цитат.
Дни 17–68 (21.11.2026 — 11.01.2027): Михаил: «сделаем как ты говоришь», «дополни сразу тем на месяц плюсом», «до 11 января».
Темы под аудиторию канала (взрослые мужчины, Казахстан) — сила, стоики, пословицы, возраст,
дружба, труд, родина, характер, зима, Новый год.

  python3 plan_h35.py            — переписывает записи слота 1 дней 17–68 в schedule_30d.json (номер и день те же,
                                   имя dDD_1L, "kind": "list"; прежняя запись — в поле "was")
  python3 plan_h35.py --back N   — откат: с дня N слот 1 снова «три мысли» (из поля "was"); потом обновить план на сервере

Подбор цитат: по порядку из cands — первые 5, которых нет в других карточках и которые не идут в других роликах
плана ближе чем за 14 дней (повтор через 2–3 дня набирает втрое меньше — playbook, Почерк тишины).
Рендер — render_list.py."""
import json
import sys
from pathlib import Path

import orchestra
from quotes_bank import QUOTES

PLAN = Path(__file__).parent / "schedule_30d.json"
ASK = "Какая — про тебя? Напиши номер в комментариях"
TAGS = "#цитаты #мудрость #жизнь #цитатыосмысле #мудрыеслова #quotes #wisdom #shorts"
GAP = 14

# день: (заголовок карточки, акварель, кандидаты по порядку, хвост названия — авторы или своё)
THEMES = {
    17: (["5 МЫСЛЕЙ, КОТОРЫЕ", "ДЕЛАЮТ СИЛЬНЕЕ"], "alpine",
         ["jpprov_seven", "plato_victory", "aurelius7_bear", "seneca6_stars", "tolstoy7_warriors"], None),
    18: (["5 ПРАВИЛ СТОИКОВ,", "КОТОРЫЕ МЕНЯЮТ ЖИЗНЬ"], "lighthouse",
         ["aurelius6_be", "seneca7_imagine", "seneca7_port", "aurelius6_last", "epictetus6_free"], None),
    19: (["5 ПОСЛОВИЦ,", "ПРОВЕРЕННЫХ ВЕКАМИ"], "steppe_horses",
         ["kzprov_knowledge", "kz7_listen", "kz7_father", "ruprov5_hands", "ruprov5_honour"], "казахская и русская мудрость"),
    20: (["С ВОЗРАСТОМ", "ПОНИМАЕШЬ:"], "lone_tree",
         ["dostoevsky_lovelife", "seneca_long", "tolstoy_wait", "ruprov5_friend", "goethe_today"], None),
    21: (["5 МЫСЛЕЙ", "О НАСТОЯЩЕЙ ДРУЖБЕ"], "cabin",
         ["emerson", "bacon7_friendship", "cervantes7_company", "ruprov5_trouble", "kz7_salt"], None),
    22: (["5 МЫСЛЕЙ", "О ВРЕМЕНИ"], "sunrise",
         ["franklin_time", "virgil7_time", "seneca7_day", "tagore_butterfly", "derzhavin_river", "khayyam7_today", "herrick7_roses"], None),
    23: (["5 МЫСЛЕЙ", "О ДЕНЬГАХ И БОГАТСТВЕ"], "canyon",
         ["dostoevsky5_money", "thoreau_price", "seneca_poor", "thoreau7_rich", "epicurus_enjoy", "ru7_money", "laozi_enough"], None),
    24: (["5 МЫСЛЕЙ", "О СЕМЬЕ И ДОМЕ"], "steppe_yurts",
         ["kzprov5_parents", "exupery_children", "wordsworth6_child", "ru7_home", "payne7_home", "holmes7_home", "upanishad7_family"], None),
    25: (["5 МЫСЛЕЙ", "О ТРУДЕ И ДЕЛЕ"], "wheat",
         ["gibran_work", "carlyle7_work", "edison_genius", "nekrasov_will", "kz7_bread", "ruprov_fish", "rumi_work"], None),
    26: (["5 МЫСЛЕЙ", "О СЛОВЕ И МОЛЧАНИИ"], "moon_sea",
         ["laozi6_speak", "zeno_ears", "kipling_words", "ru7_sparrow", "jp7_kindword", "tyutchev_silence", "buddha_word"], None),
    27: (["5 МЫСЛЕЙ", "О ТЕРПЕНИИ"], "tianshan_winter",
         ["kzprov5_patience", "lafontaine_patience", "ovid_drop", "epictetus7_fig", "ovid_pain", "aesop_slow", "augustus_hasten"], None),
    28: (["5 МЫСЛЕЙ", "О ЗНАНИИ И УЧЁБЕ"], "street_lamp",
         ["bacon7_power", "plutarch_fire", "kzprov5_knowledge", "confucius7_think", "aristotle7_roots", "leonardo_learning",
          "franklin_knowledge", "michelangelo_learn"], None),
    29: (["5 МЫСЛЕЙ", "О ДОРОГЕ И ПУТИ"], "steppe_horses",
         ["laozi_step", "balzac_walk", "af7_together", "cnprov_slow", "basho_seek", "stevenson_travel", "vivekananda7_arise"], None),
    30: (["5 МЫСЛЕЙ", "О СЧАСТЬЕ"], "almaty_lake",
         ["aristotle_happy", "korolenko_bird", "prutkov", "cn7_help", "dostoevsky_happiness", "farabi_happiness", "hugo_loved"], None),
    31: (["5 МЫСЛЕЙ", "О ДОБРОТЕ"], "winter_village",
         ["aesop", "seneca6_kindness", "henryjames7_kind", "shakespeare7_candle", "chekhov_good", "dickens_useless", "ru7_goodpeople"], None),
    32: (["5 МЫСЛЕЙ", "О СМЕЛОСТИ"], "lighthouse",
         ["seneca_dare", "montaigne_fear", "gorky_feat", "stevenson_courage", "kant_courage", "gorky_brave", "alcott_storms"], None),
    33: (["5 МЫСЛЕЙ", "О ЗИМЕ"], "frozen_lake",
         ["shelley_spring", "ruskin_weather", "no7_weather", "ru7_sledge", "ru7_frost", "confucius7_pines", "fuller7_dawn"], None),
    34: (["5 МЫСЛЕЙ", "О ХАРАКТЕРЕ"], "sea",
         ["heraclitus6_character", "confucius6_demand", "tolstoy_simple", "plutarch6_habit", "shakespeare_self", "gandhi_forgive",
          "seneca7_cruelty"], None),
    35: (["5 МЫСЛЕЙ", "О НАДЕЖДЕ"], "sunrise",
         ["cicero", "dumas_hope", "fuller7_dawn", "jp7_rain", "ko7_sky", "tagore_faith", "tyutchev_miracle"], None),
    36: (["5 МЫСЛЕЙ", "О ЛЮБВИ"], "moon_sea",
         ["shakespeare7_mind", "seneca7_love", "ovid6_lovable", "tennyson_loved", "tolstoy7_hearts", "virgil_love"], None),
    37: (["5 МЫСЛЕЙ", "О ПЕРЕМЕНАХ"], "boat_dusk",
         ["tolstoy_change", "cnprov_wind", "aurelius6_change", "lat7_times", "heraclitus_river", "cervantes7_door", "heraclitus_flow"], None),
    38: (["5 МУДРЫХ", "МЫСЛЕЙ О ЖИЗНИ"], "lone_tree",
         ["chekhov_once", "dickinson_sweet", "seneca7_play", "wilde_live", "maupassant_life", "klyuchevsky_feel", "socrates6_examined"], None),
    39: (["5 МЫСЛЕЙ", "О ПРАВДЕ И ЧЕСТИ"], "tianshan_winter",
         ["dostoevsky_lie", "prutkov7_lied", "gogol_truths", "tolstoy_greatness", "keats6_truth", "twain6_truth", "shakespeare6_honesty",
          "kz7_name", "nekrasov5_citizen"], None),
    40: (["5 УРОКОВ", "МАРКА АВРЕЛИЯ"], "dunes",
         ["aurelius7_dawn", "aurelius7_hard", "aurelius_revenge", "aurelius_within", "aurelius7_people", "aurelius7_dyed",
          "aurelius_thoughts"], "«Размышления» императора-философа"),
    41: (["5 МЫСЛЕЙ", "ЛЬВА ТОЛСТОГО"], "birch",
         ["tolstoy_thoughts", "tolstoy7_believe", "tolstoy7_life", "tolstoy_knowledge", "tolstoy_think", "tolstoy7_love", "tolstoy_moral"],
         "мудрость великого писателя"),
    42: (["5 МЫСЛЕЙ", "О РОДНОЙ ЗЕМЛЕ"], "steppe_yurts",
         ["kzprov_home", "kz7_homeland", "kz7_cradle", "prishvin7_homeland", "griboedov_smoke", "kz7_sultan", "ruprov5_home"], None),
    43: (["5 МЫСЛЕЙ", "КОНФУЦИЯ"], "moon_forest",
         ["confucius6_know", "confucius6_learn", "confucius_golden", "confucius_teacher", "confucius7_calm", "confucius_friend",
          "confucius"], "изречения из «Лунь юй»"),
    44: (["5 МЫСЛЕЙ", "СЕНЕКИ"], "sea",
         ["seneca_teach", "seneca_everywhere", "seneca_present", "seneca6_fight", "seneca7_humane", "seneca7_examples", "seneca_learn"],
         "римский философ-стоик"),
    45: (["ЗИМА В СТИХАХ:", "5 СТРОК КЛАССИКОВ"], "winter_village",
         ["tyutchev5_winter", "pushkin7_carpets", "fet7_birch", "fet5_picture", "yesenin7_sings", "nekrasov7_frost", "balmont7_flake"], None),
    46: (["5 МЫСЛЕЙ", "О МУДРОСТИ"], "canyon",
         ["socrates_know", "laozi_know", "horace_wise", "montaigne_cheer", "thales7_hard", "delphi7_know", "goethe_understand"], None),
    47: (["5 МЫСЛЕЙ", "ОБ ОПЫТЕ И ОШИБКАХ"], "boat_dusk",
         ["wilde_experience", "jpprov_monkey", "cicero_error", "kierkegaard_backwards", "ru7_straw", "livy7_late", "ruprov_morning"], None),
    48: (["5 МЫСЛЕЙ", "О СИЛЕ ДУХА"], "tianshan_winter",
         ["tennyson6_strive", "nietzsche_stronger", "nietzsche_why", "goethe6_freedom", "buddha_victory", "laozi_mighty", "verne6_despair",
          "seneca6_fight"], None),
    49: (["5 МЫСЛЕЙ", "О ТОВАРИЩЕСТВЕ"], "steppe_horses",
         ["suvorov_comrade", "gogol", "kzprov5_friends", "krylov_accord", "aesop6_unity", "cicero7_friendship", "epicurus7_friend"], None),
    50: (["5 МЫСЛЕЙ", "О ПРОСТОТЕ"], "cabin",
         ["thoreau_simplify", "yesenin_simple", "voltaire6_garden", "chekhov_brevity", "laozi_easy", "juvenal_mind", "moliere7_eat"], None),
    51: (["5 МЫСЛЕЙ", "О БЛАГОДАРНОСТИ"], "almaty_lake",
         ["cn7_source", "aesop_gratitude", "zhukovsky_were", "prutkov_keep", "cicero7_gratitude", "syrus_twice", "longfellow_give"], None),
    52: (["5 ПОСЛОВИЦ", "НАРОДОВ МИРА"], "dunes",
         ["ar7_want", "cnprov_door", "in7_boat", "jp7_frog", "tr7_coffee", "ir7_laugh", "cn7_ask", "ko7_sky"], "мудрость разных народов"),
    53: (["5 СТРОК", "РУССКОЙ КЛАССИКИ"], "birch",
         ["bunin5_passes", "griboedov_believe", "pushkin_peace", "pushkin7_master", "lermontov_struggle", "pushkin7_pora",
          "nekrasov5_citizen"], None),
    54: (["5 МЫСЛЕЙ", "О СПОКОЙСТВИИ"], "frozen_lake",
         ["epictetus", "shantideva7_worry", "horace6_anger", "proverbs_answer", "buddha_hatred", "longfellow_letrain", "spinoza_understand"],
         None),
    55: (["5 МЫСЛЕЙ", "О МЕЧТЕ И ЦЕЛИ"], "aurora",
         ["dostoevsky_purpose", "virgil6_can", "thoreau", "browning_reach", "verne_imagine", "wilde_stars", "vivekananda7_arise"], None),
    56: (["5 МЫСЛЕЙ", "ПЕРЕД НОВЫМ ГОДОМ"], "winter_village",
         ["goethe6_moment", "emerson_day", "tagore6_love", "chekhov_human", "einstein_mystery", "dickinson_sweet",
          "bunin5_passes"], None),
    57: (["С ЧЕМ ВОЙТИ", "В НОВЫЙ ГОД"], "xmas_tree",
         ["franklin6_conscience", "wilde6_saint", "stevenson7_kings", "shakespeare7_ends", "psalm7_day", "cbronte6_happy", "dickinson_sweet"],
         None),
    58: (["НОВЫЙ ГОД:", "5 МЫСЛЕЙ О НАЧАЛЕ"], "sunrise",
         ["montgomery_tomorrow", "emerson_day", "cnprov_tree", "plato_beginning", "johnson_objections", "carroll_begin",
          "psalm7_morning", "ruprov_tomorrow"], None),
    59: (["5 МЫСЛЕЙ", "О ЗДОРОВЬЕ"], "almaty_lake",
         ["juvenal_mind", "schopenhauer_health", "buddha6_health", "franklin6_early", "turgenev_health", "moliere7_eat", "socrates7_hunger"],
         None),
    60: (["МУДРОСТЬ АБАЯ:", "5 МЫСЛЕЙ"], "steppe_yurts",
         ["abai_heart", "abai_brick", "abai_son", "abai_five", "abai7_love", "abai7_boast"], "Абай Кунанбаев"),
    61: (["5 МЫСЛЕЙ", "О ВЕРЕ В СЕБЯ"], "lighthouse",
         ["nietzsche6_become", "whitman", "emerson_enthusiasm", "melville_original", "vangogh7_paint", "dante", "shakespeare_self"], None),
    62: (["5 МЫСЛЕЙ", "ОБ УМЕ"], "street_lamp",
         ["pasteur_chance", "dostoevsky_mind", "descartes_think", "goethe_understand", "buddha_thoughts", "voltaire_questions",
          "einstein_mystery"], None),
    63: (["5 МЫСЛЕЙ", "О ЩЕДРОСТИ"], "winter_village",
         ["gibran6_give", "rustaveli7_give", "syrus_twice", "longfellow_give", "in7_boat", "cn7_help", "eccl6_bread"], None),
    64: (["5 МЫСЛЕЙ", "О МИЛОСЕРДИИ"], "moon_forest",
         ["dostoevsky_compassion", "talmud_world", "dickinson_heart", "dickens_heart", "buddha7_conquer", "gandhi_forgive", "proverbs_answer"],
         None),
    65: (["5 МЫСЛЕЙ", "О ДЕЛЕ И ЛЕНИ"], "wheat",
         ["jerome_idle", "leonardo_iron", "tchaikovsky7_guest", "renard7_lazy", "ruprov_stone", "london_club", "vangogh7_small"], None),
    66: (["5 МЫСЛЕЙ", "О ВЫБОРЕ"], "canyon",
         ["ecclesiastes_wind", "ruprov_measure", "khayyam_alone", "shakespeare_doubts", "gita7_action", "kipling_if", "aesop6_greedy",
          "ru7_titmouse", "cervantes7_door"], None),
    67: (["5 МЫСЛЕЙ", "О ПАМЯТИ И ПРОШЛОМ"], "boat_dusk",
         ["austen6_past", "tolstoy_word", "gibran_yesterday", "carroll_yesterday", "fitzgerald_boats", "kierkegaard_backwards",
          "zhukovsky7_charm"], None),
    68: (["5 МЫСЛЕЙ", "О ЛЮДЯХ"], "tianshan_winter",
         ["donne_island", "terence_human", "saadi7_body", "emerson7_master", "terence7_minds", "socrates_speak", "platonov_people"], None),
}
FIXED = range(17, 22)        # уже собраны 20.11 — без перепроверки
# Михаил 20.11 12:05: «чтобы сегодня уже сегодняшние тоже по твоему правилу вышли» — 20.11 в 14:00 и 19:00 тоже карточки.
# Подбираются после всех карточек 09:00 (их цитаты не трогают).
EXTRA = {
    (16, 2): (["5 МЫСЛЕЙ, КОТОРЫЕ", "СТОИТ ЗАПОМНИТЬ"], "almaty_lake",
              ["dostoevsky_self", "newton_giants", "suvorov_training", "aesop6_help", "exupery_desert", "horace_day", "ruprov5_slow",
               "augustus_hasten"], None),
    (16, 3): (["5 МЫСЛЕЙ", "О НАСТОЯЩЕМ ЧЕЛОВЕКЕ"], "steppe_horses",
              ["chekhov_beautiful", "shakespeare_love", "voltaire_questions", "hugo6_just", "shakespeare6_honesty", "dante_origin",
               "twain6_truth", "alcott_storms"], None),
}


def target(v):
    if v["slot"] == 1 and v["day"] in THEMES:
        return THEMES[v["day"]]
    return EXTRA.get((v["day"], v["slot"]))


def flat(s):
    return s if isinstance(s, str) else " ".join(s)


def author(k, lang="ru"):
    return QUOTES[k][f"author_{lang}"].split("  ·  ")[0]


KEEP = ("Марк Аврелий", "Плиний", "Су Ши", "Евангелие", "Песнь", "Притч", "Псалтирь", "Екклесиаст", "Бхагавадгита",
        "упанишада", "Талмуд", "Дельф", "Книга")
TITLES = {   # 17–21 — как собраны 20.11
    17: "5 МЫСЛЕЙ, КОТОРЫЕ ДЕЛАЮТ СИЛЬНЕЕ ✨ Платон, Марк Аврелий, Толстой #shorts",
    18: "5 ПРАВИЛ СТОИКОВ, КОТОРЫЕ МЕНЯЮТ ЖИЗНЬ ✨ Сенека, Марк Аврелий, Эпиктет #shorts",
    19: "5 ПОСЛОВИЦ, ПРОВЕРЕННЫХ ВЕКАМИ ✨ казахская и русская мудрость #shorts",
    20: "С ВОЗРАСТОМ ПОНИМАЕШЬ: 5 простых истин ✨ Достоевский, Сенека, Толстой #shorts",
    21: "5 МЫСЛЕЙ О НАСТОЯЩЕЙ ДРУЖБЕ ✨ Эмерсон, Бэкон, Сервантес #shorts",
}


def short_name(a):
    return a if any(x in a for x in KEEP) else a.split()[-1]


def title_of(header, keys, tail):
    h = " ".join(header)
    if tail is None:
        names = [short_name(a) for a in dict.fromkeys(author(k) for k in keys) if "пословица" not in a]
        tail = ", ".join(names[:3]) if names else "народная мудрость"
    t = f"{h} ✨ {tail} #shorts"
    return t if len(t) <= 100 else f"{h} ✨ #shorts"


def describe(keys):
    lines = [f"{i + 1}. {flat(QUOTES[k]['ru'])} — {author(k)}" for i, k in enumerate(keys)]
    en = list(dict.fromkeys(author(k, "en") for k in keys))
    return ("Пять мыслей на одной карточке — сохрани, чтобы перечитать.\n" + ASK + ".\n\n" + "\n".join(lines)
            + "\n\nFive timeless thoughts: " + " · ".join(en) + ".\n\n" + TAGS)


def restore(v):
    w = v.pop("was")
    for k in ("kind", "header", "ask"):
        v.pop(k, None)
    v.update(w)


if __name__ == "__main__":
    videos = json.loads(PLAN.read_text(encoding="utf-8"))
    if "--back" in sys.argv:
        frm = int(sys.argv[sys.argv.index("--back") + 1])
        n = 0
        for v in videos:
            if v.get("kind") == "list" and v["day"] >= frm and "was" in v:
                restore(v)
                n += 1
        PLAN.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.exit(print(f"вернул «три мысли» в {n} роликов с дня {frm}"))
    # где ещё идёт цитата (кроме слота 1 дней карточек)
    uses = {}
    for v in videos:
        if target(v):
            continue
        for q in v["quotes"]:
            uses.setdefault(q, []).append(v["day"])
    taken, done, short = set(), 0, []
    order = sorted(videos, key=lambda x: (x["slot"] != 1, x["n"]))      # сначала все 09:00, потом EXTRA
    for v in order:
        if not target(v):
            continue
        header, scene, cands, tail = target(v)
        pick = []
        for k in cands:
            assert k in QUOTES, k
            if k in taken or len(pick) == 5:
                continue
            if v["day"] not in FIXED and any(abs(d - v["day"]) <= GAP for d in uses.get(k, [])):
                continue
            pick.append(k)
        if len(pick) < 5:
            short.append((v["day"], pick))
        taken.update(pick)
        if "was" not in v:
            v["was"] = {k: v[k] for k in ("quotes", "scenes", "music", "title", "description", "name") if k in v}
            if "music_was" in v:
                v["was"]["music_was"] = v["music_was"]
        base = v["was"].get("music_was") or v["was"]["music"]
        music = base if base in orchestra.STYLES else "orch_dawn"
        v.pop("music_was", None)
        v.update(kind="list", header=header, quotes=pick, scenes=[scene], music=music, ask=ASK,
                 title=(TITLES.get(v["day"]) if v["slot"] == 1 else None) or title_of(header, pick, tail), description=describe(pick),
                 name=f"d{v['day']:02d}_{v['slot']}L")
        done += 1
        print(f"{v['n']:>3} {v['date']} {v['name']} {music:<14} {v['title']}")
        for k in pick:
            print(f"      {flat(QUOTES[k]['ru'])} — {author(k)}")
    PLAN.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print("переписано записей:", done, "| не хватило цитат:", short or "нет")
