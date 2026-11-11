"""Третий месяц: дописывает в schedule_30d.json ролики №181–270 (дни 61–90, 4 января — 2 февраля 2027).
python3 plan_month3.py [seed]
Цитаты — новый банк QUOTES7 и несколько ещё не показанных старых. Правила как во втором месяце: в ролике три разных автора,
не больше одной пословицы, автор не повторяется в соседних роликах (пословицы разных народов — могут). Плюс:
 • первой (по ней название ролика) идёт «заголовочная» цитата — короткая и узнаваемая (top);
 • к датам привязаны цитаты: Новый год, Сочельник, Рождество, Крещенский вечер, Татьянин день, конец зимы;
 • ёлка — только до Старого Нового года, подснежники — только с 25 января;
 • музыка: новые стили третьего месяца (перебор фортепиано, скрипка, кларнет, саксофон) вдвое чаще прежних.
"""
import datetime as dt
import json
import random
import sys
from collections import Counter
from pathlib import Path

import quotecard as qc
from orchestra import NEW3, ORCH
from plan_schedule import DARK, TIMES, make_description, make_title
from quotes_bank import QUOTES
from quotes_bank7 import QUOTES7
from scenes3 import NEW_SCENES3

HERE = Path(__file__).parent
PLAN = HERE / "schedule_30d.json"
PREV_N, FIRST_DAY, DAYS, PER_DAY = 180, 61, 30, 3
DARK3 = set(DARK) | {"moon_forest", "street_lamp"}

# привязка к датам: ключ цитаты -> (дата, слот 1..3)
PINS = {
    "burns7_auld": ("2027-01-04", 3), "lamb7_january": ("2027-01-04", 1),
    "tennyson7_bells": ("2027-01-05", 1), "franklin7_year": ("2027-01-05", 3),
    "gogol7_christmas": ("2027-01-06", 3),
    "longfellow7_bells": ("2027-01-07", 1), "dickens7_laugh": ("2027-01-07", 2),
    "zhukovsky7_svetlana": ("2027-01-18", 3),
    "pushkin7_tatiana": ("2027-01-25", 1),
    "tyutchev7_air": ("2027-01-30", 2), "tyutchev7_waters": ("2027-01-31", 2),
    "bunin7_february": ("2027-02-01", 1), "tyutchev7_angry": ("2027-02-02", 1), "issa7_village": ("2027-02-02", 3),
}
SCENE_UNTIL = {"xmas_tree": "2027-01-14"}
SCENE_FROM = {"snowdrops": "2027-01-25"}


def group(q_):
    a = QUOTES[q_]["author_en"].split("  ·  ")[0].strip()
    return "proverb" if "proverb" in a.lower() else a


def qlen(q_):
    d = QUOTES[q_]["ru"]
    return len(d if isinstance(d, str) else " ".join(d))


def scene_ok_on(s, date):
    if s in SCENE_UNTIL and date > SCENE_UNTIL[s]:
        return False
    if s in SCENE_FROM and date < SCENE_FROM[s]:
        return False
    return s in qc.SCENES


def plan(seed):
    rnd = random.Random(seed)
    prev = [v for v in json.loads(PLAN.read_text(encoding="utf-8")) if v["n"] <= PREV_N]
    assert len(prev) == PREV_N, len(prev)
    used = {q_ for v in prev for q_ in v["quotes"]}
    keys = [k for k in QUOTES if k not in used]
    assert set(QUOTES7) <= set(keys)
    pinned_by_slot = {}
    for k, (d, s) in PINS.items():
        assert k in keys, k
        pinned_by_slot.setdefault((d, s), []).append(k)
    pool_top, pool = {}, {}
    for k in keys:
        if k in PINS:
            continue
        (pool_top if QUOTES[k].get("top") else pool).setdefault(group(k), []).append(k)
    for P in (pool_top, pool):
        for g in P:
            rnd.shuffle(P[g])
    start = dt.date.fromisoformat(prev[-1]["date"]) + dt.timedelta(days=1)
    scenes_all = list(qc.SCENES)
    new_sc = list(NEW_SCENES3)
    styles = []
    for j in range(max(len(NEW3), len(ORCH))):
        if j < len(NEW3):
            styles.append(NEW3[j])
        if j < len(ORCH):
            styles.append(ORCH[j])
        if j < len(NEW3):
            styles.append(NEW3[(j + 4) % len(NEW3)])
    style_i = rnd.randrange(len(styles))
    recent_sc = [s for v in prev[-3:] for s in v["scenes"]]
    recent_g = [group(q_) for v in prev[-2:] for q_ in v["quotes"]]
    videos = []

    def take(P, picked, avoid_recent=True):
        have = [group(p) for p in picked]
        cand = [g for g in P if P[g] and g not in have and not (g == "proverb" and "proverb" in have) and (not avoid_recent or g == "proverb" or g not in recent_g[-6:])]
        if not cand:
            return None
        w = [len(P[g]) ** 1.5 for g in cand]
        g = rnd.choices(cand, weights=w)[0]
        return P[g].pop()

    for day in range(DAYS):
        date = start + dt.timedelta(days=day)
        ds = date.isoformat()
        day_styles = []
        for slot in range(PER_DAY):
            n = PREV_N + len(videos) + 1
            picked = list(pinned_by_slot.get((ds, slot + 1), []))
            first = picked[0] if picked else None
            if not picked:
                k = take(pool_top, picked) or take(pool_top, picked, False)
                if k:
                    picked.append(k)
                    first = k
            while len(picked) < 3:
                k = take(pool, picked) or take(pool_top, picked) or take(pool, picked, False) or take(pool_top, picked, False)
                if k is None:
                    return None
                picked.append(k)
            if len({group(p) for p in picked}) < 3 or sum(group(p) == "proverb" for p in picked) > 1:
                return None
            recent_g += [group(p) for p in picked]
            rest = sorted([p for p in picked if p != first], key=qlen)
            picked = ([first] if first else []) + rest
            scenes = []
            for q_ in picked:
                d = QUOTES[q_]
                ok = lambda s: s not in scenes and s not in recent_sc[-8:] and scene_ok_on(s, ds)
                cand = [s for s in d.get("sc", []) if ok(s)]
                if not cand:   # своя картина важнее разнообразия
                    cand = [s for s in d.get("sc", []) if s not in scenes and scene_ok_on(s, ds)]
                if not cand:
                    cand = [s for s in scenes_all if ok(s)]
                    if d["mood"] == "light":
                        cand = [s for s in cand if s not in DARK3] or cand
                    elif d["mood"] == "dark":
                        cand = [s for s in cand if s in DARK3] or cand
                    fresh = [s for s in cand if s in new_sc]
                    if fresh and rnd.random() < 0.5:
                        cand = fresh
                s = rnd.choice(cand)
                scenes.append(s)
                recent_sc.append(s)
            while True:
                st = styles[style_i % len(styles)]
                style_i += 1
                if st not in day_styles:
                    break
            day_styles.append(st)
            videos.append(dict(n=n, day=FIRST_DAY + day, slot=slot + 1, date=ds, time=TIMES[slot], quotes=picked, scenes=scenes, music=st, seed=1000 + n,
                               title=make_title(picked, n), description=make_description(picked), name=f"d{FIRST_DAY + day:02d}_{slot + 1}"))
    return videos


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    videos = None
    tries = 0
    while videos is None:
        videos = plan(seed)
        seed += 1
        tries += 1
        assert tries < 500, "не сложилось"
    prev = [v for v in json.loads(PLAN.read_text(encoding="utf-8")) if v["n"] <= PREV_N]
    PLAN.write_text(json.dumps(prev + videos, ensure_ascii=False, indent=1), encoding="utf-8")
    sc = Counter(s for v in videos for s in v["scenes"])
    mu = Counter(v["music"] for v in videos)
    print(f"seed {seed - 1}: роликов {len(videos)} ({videos[0]['date']} — {videos[-1]['date']}), цитат {sum(len(v['quotes']) for v in videos)}")
    print("сцены:", sorted(sc.items(), key=lambda kv: -kv[1]))
    print("музыка:", sorted(mu.items(), key=lambda kv: -kv[1]))
    for v in videos[:6]:
        print(v["name"], v["date"], v["time"], v["music"], v["title"])
