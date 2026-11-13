"""Сводка аналитики по истории: status/report.md.

Считает по history/*.csv (то, что копит yt_check.py):
  свои каналы — подписчики (сейчас / сутки назад / неделю назад), просмотры роликов через 24 и 48 ч,
  медиана за 7 дней против прошлых 7, «застрявшие» ролики, график выкладки (МСК), лучший и худший ролик;
  соседи — выкладок в сутки, медиана просмотров роликов возрастом 2–7 дней;
  ниша — самые быстрые ролики последних сканов (просмотры в сутки) и хэштеги у топа.
Запуск: python3 tools/yt_report.py   (из корня ветки yt-status)
"""
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "history"
OUT = ROOT / "status" / "report.md"
MSK = timezone(timedelta(hours=3))


def ts(s):
    s = (s or "").strip().replace("T", " ")[:16]
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read(name):
    rows = []
    for p in sorted(HIST.glob(f"{name}-*.csv")):
        with p.open(encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    return rows


def med(xs):
    xs = [x for x in xs if x is not None]
    return int(statistics.median(xs)) if xs else None


def channels_list():
    own, rivals = [], []
    p = ROOT / "channels.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].split()
            if len(line) >= 3:
                (own if line[2] == "своя" else rivals).append((line[0].lstrip("@"), line[1]))
    return own, rivals


def views_at(points, pub, hours):
    """Просмотры в момент pub+hours по снимкам (линейно между соседними снимками). None, если нет снимков по обе стороны."""
    target = pub + timedelta(hours=hours)
    before = [(t, v) for t, v in points if t <= target]
    after = [(t, v) for t, v in points if t >= target]
    if not after:
        return None
    if not before:
        t1, v1 = after[0]
        return v1 if (t1 - target) <= timedelta(hours=6) else None
    (t0, v0), (t1, v1) = before[-1], after[0]
    if t1 == t0:
        return v0
    if (t1 - t0) > timedelta(hours=36):
        return None
    return int(v0 + (v1 - v0) * (target - t0) / (t1 - t0))


def main():
    now = datetime.now(timezone.utc)
    own, rivals = channels_list()
    ch_rows = read("channels")
    v_rows = read("videos")

    subs = defaultdict(list)
    for r in ch_rows:
        t = ts(r["checked_utc"])
        if t and r.get("subs") not in (None, "", "None"):
            subs[r["handle"]].append((t, int(r["subs"])))

    vids = defaultdict(lambda: {"points": [], "pub": None, "title": "", "handle": ""})
    for r in v_rows:
        t = ts(r["checked_utc"])
        if not t or r.get("views") in (None, "", "None"):
            continue
        v = vids[r["video_id"]]
        v["handle"] = r["handle"]
        v["title"] = r["title"] or v["title"]
        if r.get("published_utc"):
            v["pub"] = ts(r["published_utc"]) or v["pub"]
        if r["src"] == "rss":
            v["points"].append((t, int(r["views"])))
    for v in vids.values():
        v["points"] = sorted(set(v["points"]))

    md = [f"# Сводка аналитики · {now.astimezone(MSK):%d.%m.%Y %H:%M} МСК", "",
          "Считано по history/*.csv. Просмотры через 24/48 ч — по снимкам (чем чаще снимки, тем точнее).", ""]

    md += ["## Свои каналы", "",
           "| канал | подписчики | за сутки | за 7 дн | роликов за 7 дн | медиана 24 ч (7 дн / прошлые 7) | медиана 48 ч | застряли <100 за 48 ч |",
           "|---|---|---|---|---|---|---|---|"]
    details = []
    for h, niche in own:
        s = sorted(subs.get(h, []))
        cur = s[-1][1] if s else None
        if s and now - s[-1][0] > timedelta(hours=30):
            s = []  # данные устарели — прирост не считать

        def ago(hours):
            older = [x for x in s if x[0] <= now - timedelta(hours=hours)]
            return older[-1][1] if older else None
        d1 = (cur - ago(24)) if cur is not None and ago(24) is not None else None
        d7 = (cur - ago(168)) if cur is not None and ago(168) is not None else None
        mine = [(vid, v) for vid, v in vids.items() if v["handle"] == h and v["pub"]]
        last7 = [(vid, v) for vid, v in mine if now - timedelta(days=7) <= v["pub"]]
        prev7 = [(vid, v) for vid, v in mine if now - timedelta(days=14) <= v["pub"] < now - timedelta(days=7)]
        m24a = med([views_at(v["points"], v["pub"], 24) for _, v in last7])
        m24b = med([views_at(v["points"], v["pub"], 24) for _, v in prev7])
        m48 = med([views_at(v["points"], v["pub"], 48) for _, v in last7 + prev7])
        old48 = [(vid, v) for vid, v in last7 + prev7 if now - v["pub"] >= timedelta(hours=48)]
        stuck = [1 for _, v in old48 if (views_at(v["points"], v["pub"], 48) or (v["points"][-1][1] if v["points"] else 0)) < 100]
        stuck_txt = f"{len(stuck)} из {len(old48)}" if old48 else "—"
        trend = ""
        if m24a is not None and m24b:
            ch = (m24a - m24b) / m24b
            trend = " 🔻" if ch < -0.3 else (" 🔺" if ch > 0.3 else "")
        md.append(f"| {h} ({niche}) | {cur if cur is not None else '?'} | {d1 if d1 is not None else '?'} | "
                  f"{d7 if d7 is not None else '?'} | {len(last7)} | {m24a if m24a is not None else '?'} / "
                  f"{m24b if m24b is not None else '?'}{trend} | {m48 if m48 is not None else '?'} | {stuck_txt} |")
        if last7:
            by_day = Counter(v["pub"].astimezone(MSK).strftime("%d.%m") for _, v in last7)
            hours = Counter(v["pub"].astimezone(MSK).strftime("%H") for _, v in last7)
            ranked = sorted(last7, key=lambda x: x[1]["points"][-1][1] if x[1]["points"] else 0)
            aged = [x for x in ranked if now - x[1]["pub"] >= timedelta(hours=24)] or ranked
            best, worst = aged[-1], aged[0]
            details.append(f"**{h}** — выкладки по дням: " + ", ".join(f"{d}: {n}" for d, n in sorted(by_day.items()))
                           + "; часы (МСК): " + ", ".join(f"{hh}ч×{n}" for hh, n in sorted(hours.items())))
            details.append(f"  - лучший: {best[1]['points'][-1][1] if best[1]['points'] else '?'} — {best[1]['title'][:80]} ({best[0]})")
            details.append(f"  - худший: {worst[1]['points'][-1][1] if worst[1]['points'] else '?'} — {worst[1]['title'][:80]} ({worst[0]})")
            gaps = sorted(v["pub"] for _, v in last7)
            bursts = sum(1 for a, b in zip(gaps, gaps[1:]) if b - a < timedelta(hours=1))
            if bursts:
                details.append(f"  - ⚠️ ролики с промежутком меньше часа: {bursts} раз")
    md += [""] + details

    if rivals:
        md += ["", "## Соседи", "", "| канал | ниша | подписчики | роликов за 7 дн | медиана просмотров (возраст 2–7 дн) |",
               "|---|---|---|---|---|"]
        for h, niche in rivals:
            s = sorted(subs.get(h, []))
            mine = [v for v in vids.values() if v["handle"] == h and v["pub"]]
            n7 = sum(1 for v in mine if v["pub"] >= now - timedelta(days=7))
            mm = med([v["points"][-1][1] for v in mine if v["points"] and timedelta(days=2) <= now - v["pub"] <= timedelta(days=7)])
            md.append(f"| {h} | {niche} | {s[-1][1] if s else '?'} | {n7} | {mm if mm is not None else '?'} |")

    scans_dir = ROOT / "status" / "scans"
    fast, tags = [], Counter()
    for p in sorted(scans_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for it in d.get("items", [])[:30]:
            if it.get("per_day") and it.get("age_h") and it["age_h"] <= 24 * 14:
                fast.append((it["per_day"], d["spec"], it))
            for t in it.get("tags") or []:
                tags[(d["spec"].split(":", 1)[1], t)] += 1
    if fast:
        md += ["", "## Ниши: самые быстрые ролики (до 14 дней, просмотров в сутки)", "",
               "| в сутки | скан | канал (подписчики) | просм. | возраст | название |", "|---|---|---|---|---|---|"]
        seen = set()
        for pd, spec, it in sorted(fast, key=lambda x: -x[0]):
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            md.append(f"| {pd} | {spec} | {it.get('channel') or '?'} ({it.get('channel_subs') or '?'}) | {it.get('views')} | "
                      f"{it['age_h'] / 24:.1f} дн | {(it.get('title') or '').replace('|', '/')[:70]} |")
            if len(seen) >= 20:
                break
    if tags:
        by_q = defaultdict(list)
        for (q, t), n in tags.most_common():
            if t != "#shorts" and len(by_q[q]) < 10:
                by_q[q].append(f"{t}×{n}")
        md += ["", "## Хэштеги у топа выдачи (по запросам)", ""] + [f"- {q}: " + ", ".join(v) for q, v in by_q.items()]

    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"report: {OUT}")


if __name__ == "__main__":
    main()
