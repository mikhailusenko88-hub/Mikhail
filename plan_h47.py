"""H47 (26.11.2026, «да» Михаила): вторая карточка «5 мыслей» в день — слот 19:00 МСК вместо трёх цитат.
Дни 23–29 (27.11 — 03.12.2026), 7 дней. Зачем: карточка 09:00 (H35) выигрывает свой слот вдвое,
но день канала почти не вырос — старые слоты теряют. У «Білесің бе?» день вырос ~в 2,5 раза, когда
сильный формат занял 2 слота из 3 (H30). Мерка H47 — сумма просмотров канала за день против 22–26.11.

  python3 plan_h47.py            — переписывает записи слота 3 дней 23–29 в schedule_30d.json
                                   (имя dDD_3L, "kind": "list"; прежняя запись — в поле "was")
  python3 plan_h47.py --back N   — откат: с дня N слот 3 снова «три мысли»; потом обновить план на сервере

В отличие от plan_h35.py не трогает другие записи плана (карточки 09:00 уже собраны — их подбор не пересчитывается).
Цитаты: первые 5 из кандидатов, которых нет ни в одной карточке и которые не идут в других роликах ближе 14 дней.
Рендер — render_list.py <день> 3."""
import json
import sys

import orchestra
from plan_h35 import ASK, GAP, PLAN, QUOTES, describe, flat, author, restore, title_of

DAYS = range(23, 30)
SLOT = 3
THEMES = {
    23: (["5 МЫСЛЕЙ", "О РАДОСТИ"], "almaty_lake",
         ["twain6_cheer", "chamfort7_laugh", "dickens7_laugh", "proverbs6_heart", "democritus7_feasts", "blake7_joy",
          "wilcox7_laugh", "schiller7_joy"], None),
    24: (["5 КРЫЛАТЫХ ФРАЗ,", "КОТОРЫЕ ЗНАЕТ КАЖДЫЙ"], "boat_dusk",
         ["griboedov7_tongues", "krylov7_casket", "ilf_drowning", "bulgakov_manuscripts", "krylov7_elephant", "krylov_gossip",
          "prutkov_root", "gorky5_crawl"], "Грибоедов, Крылов, Булгаков"),
    25: (["5 МЫСЛЕЙ", "О ВЕРНОСТИ"], "lighthouse",
         ["macdonald7_trust", "ruth7_go", "shakespeare7_mark", "kipling7_blood", "coleridge7_tree", "dumas6_all",
          "gibran7_friend", "austen6_friends"], None),
    26: (["5 МЫСЛЕЙ", "О ДОСТОИНСТВЕ"], "sea",
         ["cervantes_works", "thoreau6_good", "exupery7_answer", "shakespeare6_may", "chekhov_clear", "exupery_ask",
          "pushkin7_praise", "diogenes7_human"], None),
    27: (["5 ПОСЛОВИЦ", "О ГЛАВНОМ"], "steppe_horses",
         ["kzprov5_roots", "kz7_guest", "kz7_crafts", "ru7_tongue", "ru7_peace", "kzprov5_unity", "ruprov5_luck",
          "ru7_early"], "казахская и русская мудрость"),
    28: (["5 МЫСЛЕЙ", "О ПРИРОДЕ"], "aurora",
         ["turgenev5_workshop", "emerson6_flowers", "muir7_mountains", "whitman6_grass", "burnett7_garden", "muir7_walk",
          "keats7_earth", "kilmer7_tree"], None),
    29: (["5 МЫСЛЕЙ", "О ДЕТСТВЕ"], "winter_village",
         ["mencius7_child", "tagore6_child", "schiller_play", "andersen_fairytale", "issa7_village", "carroll6_impossible",
          "barrie7_star", "pushkin5_tale"], None),
}


def is_target(v):
    return v["slot"] == SLOT and v["day"] in THEMES


if __name__ == "__main__":
    videos = json.loads(PLAN.read_text(encoding="utf-8"))
    if "--back" in sys.argv:
        frm = int(sys.argv[sys.argv.index("--back") + 1])
        n = 0
        for v in videos:
            if is_target(v) and v.get("kind") == "list" and v["day"] >= frm and "was" in v:
                restore(v)
                n += 1
        PLAN.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.exit(print(f"вернул «три мысли» в {n} роликов слота 19:00 с дня {frm}"))
    uses, taken = {}, set()
    for v in videos:
        if is_target(v):
            continue
        if v.get("kind") == "list":
            taken.update(v["quotes"])
        for q in v["quotes"]:
            uses.setdefault(q, []).append(v["day"])
    done, short = 0, []
    for v in sorted(videos, key=lambda x: x["n"]):
        if not is_target(v):
            continue
        header, scene, cands, tail = THEMES[v["day"]]
        pick = []
        for k in cands:
            assert k in QUOTES, k
            if k in taken or len(pick) == 5:
                continue
            if any(abs(d - v["day"]) <= GAP for d in uses.get(k, [])):
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
                 title=title_of(header, pick, tail), description=describe(pick), name=f"d{v['day']:02d}_{SLOT}L")
        done += 1
        print(f"{v['n']:>3} {v['date']} {v['time']} {v['name']} {music:<14} {v['title']}")
        for k in pick:
            print(f"      {flat(QUOTES[k]['ru'])} — {author(k)}")
    PLAN.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print("переписано записей:", done, "| не хватило цитат:", short or "нет")
