"""Второй месяц: дописывает в schedule_30d.json ролики №91–180 (дни 31–60) из цитат, которых не было в первом месяце.
python3 plan_month2.py [seed]
Правила: в ролике три разных автора, не больше одной пословицы, автор не повторяется в соседних роликах;
у цитаты с пометкой sc картина берётся из подходящих (зимние стихи — к зиме), новые сцены в приоритете."""
import datetime as dt
import json
import random
import sys
from collections import Counter
from pathlib import Path

import quotecard as qc
from orchestra import ORCH
from plan_schedule import DARK, TIMES, make_description, make_title
from quotes_bank import QUOTES
from scenes2 import NEW_SCENES

HERE = Path(__file__).parent
PLAN = HERE / "schedule_30d.json"
FIRST_N, DAYS, PER_DAY = 90, 30, 3


def group(q_):
    a = QUOTES[q_]["author_en"].split("  ·  ")[0].strip()
    return "proverb" if "proverb" in a.lower() else a


def qlen(q_):
    d = QUOTES[q_]["ru"]
    return len(d if isinstance(d, str) else " ".join(d))


def plan(seed):
    rnd = random.Random(seed)
    month1 = [v for v in json.loads(PLAN.read_text(encoding="utf-8")) if v["n"] <= FIRST_N]
    used = {q_ for v in month1 for q_ in v["quotes"]}
    pool = {}
    for q_ in QUOTES:
        if q_ not in used:
            pool.setdefault(group(q_), []).append(q_)
    for g in pool:
        rnd.shuffle(pool[g])
    start = dt.date.fromisoformat(month1[-1]["date"]) + dt.timedelta(days=1)
    scenes_all = list(qc.SCENES)
    new_sc = list(NEW_SCENES)
    styles = list(ORCH)
    style_i = FIRST_N + 1
    recent_sc = [s for v in month1[-3:] for s in v["scenes"]]
    recent_g = []
    videos = []
    for day in range(DAYS):
        day_styles = []
        for slot in range(PER_DAY):
            n = FIRST_N + len(videos) + 1
            picked = []
            for _ in range(3):
                cand = [g for g in pool if pool[g] and g not in [group(p) for p in picked] and g not in recent_g[-6:]]
                if not cand:
                    cand = [g for g in pool if pool[g] and g not in [group(p) for p in picked]]
                if not cand:
                    return None
                w = [len(pool[g]) ** 1.5 for g in cand]
                g = rnd.choices(cand, weights=w)[0]
                picked.append(pool[g].pop())
            recent_g += [group(p) for p in picked]
            picked.sort(key=qlen)
            scenes = []
            for q_ in picked:
                d = QUOTES[q_]
                ok = lambda s: s not in scenes and s not in recent_sc[-8:]
                cand = [s for s in d.get("sc", []) if s in qc.SCENES and ok(s)]
                if not cand:   # своя картина важнее разнообразия
                    cand = [s for s in d.get("sc", []) if s in qc.SCENES and s not in scenes]
                if not cand:
                    cand = [s for s in scenes_all if ok(s)]
                    if d["mood"] == "light":
                        cand = [s for s in cand if s not in DARK] or cand
                    elif d["mood"] == "dark":
                        cand = [s for s in cand if s in DARK] or cand
                    fresh = [s for s in cand if s in new_sc]
                    if fresh and rnd.random() < 0.45:
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
            date = start + dt.timedelta(days=day)
            videos.append(dict(n=n, day=31 + day, slot=slot + 1, date=date.isoformat(), time=TIMES[slot], quotes=picked, scenes=scenes, music=st, seed=1000 + n,
                               title=make_title(picked, n), description=make_description(picked), name=f"d{31 + day:02d}_{slot + 1}"))
    return videos


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    videos = None
    while videos is None:
        videos = plan(seed)
        seed += 1
    month1 = [v for v in json.loads(PLAN.read_text(encoding="utf-8")) if v["n"] <= FIRST_N]
    PLAN.write_text(json.dumps(month1 + videos, ensure_ascii=False, indent=1), encoding="utf-8")
    sc = Counter(s for v in videos for s in v["scenes"])
    print(f"seed {seed - 1}: роликов {len(videos)} ({videos[0]['date']} — {videos[-1]['date']}), цитат {sum(len(v['quotes']) for v in videos)}")
    print("сцены:", sorted(sc.items(), key=lambda kv: -kv[1]))
    for v in videos[:4]:
        print(v["name"], v["date"], v["time"], v["title"])
