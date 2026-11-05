"""Сезон на выживание: 193 страны → отбор (7 заездов, выживают 96) → 2-й тур (3×32, по 16) → полуфиналы (2×24, по 16)
→ гранд-финал (32, один чемпион). Потом новый сезон со всеми странами. Состояние — season_state.json."""
import copy
import datetime as dt
import json
import os
import random

import countries

TOTAL = len(countries.COUNTRIES)
R1_HEATS, R1_SURVIVE = 7, 96
ROUND_NAMES = {1: "ROUND 1", 2: "ROUND 2", 3: "SEMI-FINAL", 4: "GRAND FINAL"}
ROUND_SHORT = {1: "ROUND 1", 2: "ROUND 2", 3: "SEMI-FINALS", 4: "GRAND FINAL"}
NSTAGES = {1: 3, 2: 3, 3: 2}
FINAL_STAGES = [(32, 26), (26, 20), (20, 15), (15, 10), (10, 6), (6, 3), (3, 3)]
SLOT_HOURS = {1: 7, 2: 15, 3: 23}          # МСК, когда ролик выходит


def load(path):
    return json.load(open(path))


def save(state, path):
    tmp = path + ".tmp"
    json.dump(state, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def split(codes, n):
    """Делит список на n кусков, размеры отличаются не больше чем на 1 (большие — первыми)."""
    q, r = divmod(len(codes), n)
    out, i = [], 0
    for j in range(n):
        m = q + (1 if j < r else 0)
        out.append(codes[i:i + m])
        i += m
    return out


def alloc(sizes, total):
    """Сколько выживает в каждом заезде, чтобы в сумме было total (пропорционально, наибольшие остатки)."""
    s = sum(sizes)
    exact = [x * total / s for x in sizes]
    base = [int(e) for e in exact]
    left = total - sum(base)
    for j in sorted(range(len(sizes)), key=lambda j: -(exact[j] - base[j]))[:left]:
        base[j] += 1
    return base


def _rng(state, *k):
    return random.Random(state["seed"] * 100003 + state["season"] * 1009 + sum(x * 7919 ** n for n, x in enumerate(k)))


def start_round(state, rnd):
    state["round"], state["heat"] = rnd, 0
    if rnd == 1:
        codes = [a2 for a2, _ in countries.COUNTRIES]
        _rng(state, 1).shuffle(codes)
        state["heats"] = split(codes, R1_HEATS)
        state["survive"] = alloc([len(h) for h in state["heats"]], R1_SURVIVE)
        state["survivors"], state["eliminated"] = [], []
    else:
        pool = list(state["survivors"])
        _rng(state, rnd).shuffle(pool)
        n = {2: 3, 3: 2, 4: 1}[rnd]
        state["heats"] = split(pool, n)
        state["survive"] = [1] if rnd == 4 else [16] * n
        state["survivors"] = []


def stages_for(n, k, rnd):
    if rnd == 4:
        return FINAL_STAGES
    ns = NSTAGES[rnd]
    cnt = [n] + [round(n - (n - k) * j / ns) for j in range(1, ns + 1)]
    return list(zip(cnt[:-1], cnt[1:]))


def current(state):
    """Что за гонка следующая: раунд, заезд, участники, сколько выживает, этапы."""
    rnd, h = state["round"], state["heat"]
    codes = list(state["heats"][h])
    k = state["survive"][h]
    return {"season": state["season"], "round": rnd, "round_name": ROUND_NAMES[rnd], "heat": h + 1,
            "heats": len(state["heats"]), "codes": codes, "survive": k, "final": rnd == 4,
            "stages": stages_for(len(codes), k, rnd), "alive": TOTAL - len(state["eliminated"]),
            "race_no": state["race_no"] + 1}


def label(p):
    if p["final"]:
        return f"SEASON {p['season']} · GRAND FINAL"
    return f"{p['round_name']} · HEAT {p['heat']}/{p['heats']}" if p["heats"] > 1 else p["round_name"]


def apply(state, plan, ranking, d, slot):
    """ranking — коды от 1-го места к последнему. Двигает сезон вперёд."""
    k = plan["survive"]
    state["race_no"] += 1
    surv, out = ranking[:k], ranking[k:]
    state["survivors"] += surv
    state["eliminated"] += out
    state["history"].append({"no": state["race_no"], "date": d.isoformat(), "slot": slot, "season": plan["season"],
                             "round": plan["round"], "heat": plan["heat"], "ranking": ranking, "survive": k})
    for c in ranking:
        r = state["hall"].setdefault(c, {"titles": 0, "finals": 0})
        if plan["final"]:
            r["finals"] += 1
    if plan["final"]:
        state["hall"][ranking[0]]["titles"] += 1
        state["champions"].append({"season": plan["season"], "code": ranking[0], "podium": ranking[:3],
                                   "date": d.isoformat()})
        state["season"] += 1
        start_round(state, 1)
        return
    state["heat"] += 1
    if state["heat"] >= len(state["heats"]):
        start_round(state, state["round"] + 1)


def peek_after(state, plan, ranking, d, slot):
    s = copy.deepcopy(state)
    apply(s, plan, ranking, d, slot)
    return current(s), s


def remaining_to_final(state_after):
    """Сколько гонок осталось до гранд-финала (включая его) в текущем сезоне."""
    s = state_after
    if s["round"] == 4:
        return 1
    n = len(s["heats"]) - s["heat"]
    for r in range(s["round"] + 1, 4):
        n += {2: 3, 3: 2}[r]
    return n + 1


def slot_after(d, slot, n):
    """Дата и слот через n гонок (3 в день)."""
    k = (slot - 1) + n
    return d + dt.timedelta(days=k // 3), k % 3 + 1


def init_from_league(league_path, out_path):
    """Сезон 1: гонка #1 (32 страны) уже прошла — это заезд 1, выживают 15 (дошли до 4-го этапа).
    Остальные 161 страна — в 6 заездах по очереди из старой лиги (первые 27 — те, кого анонсировал ролик #1)."""
    old = json.load(open(league_path))
    h1 = old["history"][0]
    r1 = h1["ranking"]
    rest = list(old["queue"])
    assert len(r1) == 32 and len(rest) == 161 and not set(r1) & set(rest)
    heats = [list(r1)] + split(rest, 6)
    survive = [15] + alloc([len(h) for h in heats[1:]], R1_SURVIVE - 15)
    state = {"season": 1, "race_no": 1, "seed": old["seed"], "round": 1, "heat": 1, "heats": heats,
             "survive": survive, "survivors": r1[:15], "eliminated": r1[15:], "champions": [], "hall": {},
             "history": [{"no": 1, "date": h1["date"], "slot": 1, "season": 1, "round": 1, "heat": 1,
                          "ranking": r1, "survive": 15}]}
    save(state, out_path)
    return state


if __name__ == "__main__":
    import sys
    st = init_from_league(sys.argv[1], sys.argv[2])
    print([len(h) for h in st["heats"]], st["survive"], sum(st["survive"]))
