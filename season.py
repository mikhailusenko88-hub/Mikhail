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


# ============================================================ сезон «3 жизни» (с сезона 2)
# У каждой страны 3 жизни. Гонка — 24 страны (сначала те, кто бежал меньше всех), нижние L теряют жизнь,
# без жизней — вылет. L подбирается сам, чтобы к финалу (фиксированное число гонок) осталось ~40 стран.
# Гранд-финал — 32 лучшие по жизням (при равенстве — по среднему месту). Финал в дату, обещанную зрителям.
LIVES = 3
LIFE_HEAT = 24
FINALISTS = 32
TARGET_ALIVE = 40          # сколько стран примерно доживает до финала (борьба за 32 места)


def is_lives(state):
    return state.get("mode") == "lives"


def alive_codes(state):
    return [c for c, v in state["lives"].items() if v > 0]


def _life_losers(state, n):
    """Сколько стран теряет жизнь в этой гонке: чтобы к финалу осталось ~TARGET_ALIVE стран."""
    left = max(1, state["life_total"] - state["heat"])
    lives_now = sum(v for v in state["lives"].values() if v > 0)
    want = TARGET_ALIVE * 1.6                       # у доживших в среднем ~1,6 жизни
    L = round((lives_now - want) / left)
    return max(2, min(n // 2, L))


def _life_heat(state):
    pool = alive_codes(state)
    r = _rng(state, 7, state["heat"] + 1)
    r.shuffle(pool)
    pool.sort(key=lambda c: state["raced"].get(c, 0))   # кто бежал меньше — тот первый
    return pool[:LIFE_HEAT]


def finalists(state):
    al = alive_codes(state)
    sc = state["score"]
    return sorted(al, key=lambda c: (-state["lives"][c], -sc.get(c, 0) / max(1, state["raced"].get(c, 0)), c))[:FINALISTS]


def start_lives_season(state, life_total, prior=None):
    """Новый сезон «3 жизни». prior — уже прошедшие гонки этого сезона по старым правилам (их учитываем)."""
    state.update({"mode": "lives", "round": 1, "heat": 0, "life_total": life_total,
                  "lives": {a2: LIVES for a2, _ in countries.COUNTRIES}, "raced": {}, "score": {},
                  "heats": [], "survive": [], "survivors": [], "eliminated": []})


def _life_current(state):
    if state["round"] == 4:
        codes = list(state["heats"][0])
        return {"season": state["season"], "round": 4, "round_name": ROUND_NAMES[4], "heat": 1, "heats": 1,
                "codes": codes, "survive": 1, "final": True, "stages": stages_for(len(codes), 1, 4) if len(codes) == 32
                else _final_stages(len(codes)), "alive": len(alive_codes(state)), "race_no": state["race_no"] + 1,
                "lives_mode": True, "lives": {c: state["lives"][c] for c in codes}, "life_total": state["life_total"]}
    codes = _life_heat(state)
    n = len(codes)
    L = _life_losers(state, n)
    return {"season": state["season"], "round": 1, "round_name": "RACE", "heat": state["heat"] + 1,
            "heats": state["life_total"], "codes": codes, "survive": n - L, "final": False,
            "stages": stages_for(n, n - L, 1), "alive": len(alive_codes(state)), "race_no": state["race_no"] + 1,
            "lives_mode": True, "lives": {c: state["lives"][c] for c in codes}, "life_total": state["life_total"]}


def _final_stages(n):
    """Этапы финала, если финалистов не 32 (запасной случай)."""
    cnt = [n]
    while cnt[-1] > 3:
        cnt.append(max(3, round(cnt[-1] * 0.75)))
    st = list(zip(cnt[:-1], cnt[1:]))
    return st + [(3, 3)]


def _life_apply(state, plan, ranking, d, slot):
    n = len(ranking)
    k = plan["survive"]
    state["race_no"] += 1
    state["history"].append({"no": state["race_no"], "date": d.isoformat(), "slot": slot, "season": plan["season"],
                             "round": plan["round"], "heat": plan["heat"], "ranking": ranking, "survive": k,
                             "mode": "lives"})
    if plan["final"]:
        for c in ranking:
            state["hall"].setdefault(c, {"titles": 0, "finals": 0})["finals"] += 1
        state["hall"][ranking[0]]["titles"] += 1
        state["champions"].append({"season": plan["season"], "code": ranking[0], "podium": ranking[:3],
                                   "date": d.isoformat()})
        state["season"] += 1
        start_lives_season(state, state.get("next_life_total", state["life_total"]))
        return
    for i, c in enumerate(ranking):
        state["raced"][c] = state["raced"].get(c, 0) + 1
        state["score"][c] = state["score"].get(c, 0) + (n - 1 - i) / max(1, n - 1)
    alive = len(alive_codes(state))
    for c in ranking[k:]:                       # от лучшего из проигравших к худшему
        if state["lives"][c] == 1 and alive <= FINALISTS:
            continue                            # меньше 32 не опускаемся — финал всегда полный
        state["lives"][c] -= 1
        if state["lives"][c] == 0:
            alive -= 1
            state["eliminated"].append(c)
    state["heat"] += 1
    if state["heat"] >= state["life_total"]:
        state["round"], state["heats"], state["survive"] = 4, [finalists(state)], [1]


def races_until(d, slot, final_d, final_slot):
    """Сколько выкладок от (d, slot) включительно до финала (не включая сам финал)."""
    return (final_d - d).days * 3 + (final_slot - slot)


def migrate_to_lives(state, next_d, next_slot, final_d, final_slot=3):
    """Перевод текущего сезона на «3 жизни». Гонки этого сезона, уже прошедшие по старым правилам, засчитываются:
    кто в них вылетел — минус жизнь."""
    done = [h for h in state["history"] if h["season"] == state["season"]]
    start_lives_season(state, races_until(next_d, next_slot, final_d, final_slot) + len(done))
    for h in done:
        r, k, n = h["ranking"], h["survive"], len(h["ranking"])
        for i, c in enumerate(r):
            state["raced"][c] = state["raced"].get(c, 0) + 1
            state["score"][c] = state["score"].get(c, 0) + (n - 1 - i) / max(1, n - 1)
        for c in r[k:]:
            state["lives"][c] -= 1
        h["lives_heat"] = True
    state["heat"] = len(done)
    state["final_date"] = final_d.isoformat()
    return state


def life_lost(before_plan, after_state):
    """Кто в этой гонке потерял жизнь и сколько осталось: {код: жизней после}."""
    return {c: after_state["lives"][c] for c in before_plan["codes"]
            if after_state["lives"][c] < before_plan["lives"][c]}


def current(state):
    """Что за гонка следующая: раунд, заезд, участники, сколько выживает, этапы."""
    if is_lives(state):
        return _life_current(state)
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
    if p.get("lives_mode"):
        return f"RACE {p['heat']}/{p['heats']}"
    return f"{p['round_name']} · HEAT {p['heat']}/{p['heats']}" if p["heats"] > 1 else p["round_name"]


def apply(state, plan, ranking, d, slot):
    """ranking — коды от 1-го места к последнему. Двигает сезон вперёд."""
    if is_lives(state):
        return _life_apply(state, plan, ranking, d, slot)
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
    if is_lives(s):
        return s["life_total"] - s["heat"] + 1
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
