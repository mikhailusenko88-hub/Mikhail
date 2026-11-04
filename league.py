"""Лига: каждый день 32 страны (по очереди из 193), общая таблица месяца, финал месяца — топ-32 в последний день."""
import calendar
import datetime as dt
import json
import os
import random

import countries

SLOTS_PER_DAY = 3
POINTS = [25, 18, 15, 12, 10, 8, 6, 5, 4, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1] + [0] * 12
MONTHS_EN = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER",
             "NOVEMBER", "DECEMBER"]


def new_state(seed=2026):
    return {"race_no": 0, "seed": seed, "cycle": 0, "queue": [], "month": None, "table": {}, "alltime": {},
            "champions": [], "history": []}


def load(path):
    if os.path.exists(path):
        return json.load(open(path))
    return new_state()


def save(state, path):
    tmp = path + ".tmp"
    json.dump(state, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def month_key(d):
    return f"{d.year}-{d.month:02d}"


def final_date(d):
    return dt.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def is_final_day(d):
    return d == final_date(d)


def sorted_table(table):
    return sorted(table.items(), key=lambda kv: (-kv[1]["pts"], -kv[1]["wins"], kv[1]["best"], kv[0]))


def _refill(state):
    codes = [a2 for a2, _ in countries.COUNTRIES]
    rng = random.Random(state["seed"] * 1000 + state["cycle"])
    rng.shuffle(codes)
    state["cycle"] += 1
    state["queue"] += codes


def next_slot(d, slot):
    return (d, slot + 1) if slot < SLOTS_PER_DAY else (d + dt.timedelta(days=1), 1)


def is_final_slot(d, slot):
    return is_final_day(d) and slot == SLOTS_PER_DAY


def peek_participants(state, d, slot=1):
    """Кто бежит в гонке (день d, слот 1..3), не меняя состояние. Финал месяца — последний слот последнего дня."""
    same_month = state.get("month") == month_key(d)
    if is_final_slot(d, slot) and same_month and len(state["table"]) >= 32:
        return "final", [c for c, _ in sorted_table(state["table"])[:32]]
    q = list(state["queue"])
    tmp = dict(state, queue=q, cycle=state["cycle"])
    while len(q) < 32:
        _refill(tmp)
        q = tmp["queue"]
    picked = []
    for c in q:
        if c not in picked:
            picked.append(c)
        if len(picked) == 32:
            break
    return "daily", picked


def take_participants(state, d, slot=1):
    if state.get("month") != month_key(d):
        state["month"] = month_key(d)
        state["table"] = {}
    kind, picked = peek_participants(state, d, slot)
    if kind == "daily":
        while len(state["queue"]) < 32:
            _refill(state)
        for c in picked:
            state["queue"].remove(c)
    return kind, picked


def _row(t, c):
    return t.setdefault(c, {"pts": 0, "races": 0, "wins": 0, "pod": 0, "best": 99, "titles": 0})


def apply_result(state, d, kind, ranking, slot=1):
    """ranking — коды стран от 1-го места к последнему. Возвращает очки этой гонки."""
    state["race_no"] += 1
    gained = {}
    for place, c in enumerate(ranking, 1):
        p = POINTS[place - 1] if kind == "daily" else 0
        gained[c] = p
        tables = [state["alltime"]] + ([state["table"]] if kind == "daily" else [])
        for t in tables:
            r = _row(t, c)
            r["pts"] += p
            r["races"] += 1
            r["wins"] += place == 1
            r["pod"] += place <= 3
            r["best"] = min(r["best"], place)
    if kind == "final":
        state["champions"].append({"month": state["month"], "code": ranking[0], "second": ranking[1], "third": ranking[2]})
        _row(state["alltime"], ranking[0])["titles"] += 1
    state["history"].append({"no": state["race_no"], "date": d.isoformat(), "slot": slot, "kind": kind, "ranking": ranking})
    return gained
