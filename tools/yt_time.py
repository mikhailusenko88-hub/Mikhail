"""Время выхода роликов: как набирают просмотры по часам после выхода и по календарным дням МСК.

  python3 tools/yt_time.py cartoon_friend3                 — все ролики канала за месяц (без Shorts у длинных каналов: --long)
  python3 tools/yt_time.py cartoon_friend3 --long --since 2026-11-17
  python3 tools/yt_time.py FlagballArenaTV --since 2026-11-20

Для каждого ролика: время выхода (МСК, день недели), просмотры через 6/12/24/48/96 ч (между снимками — по прямой;
«—», если рядом нет снимка), «тишина» — последний снимок с <20 просмотрами и первый с ≥20 (сколько часов после выхода
YouTube почти не показывал ролик), «день 0 / день 1» — сколько набрал в день выхода и на следующий день по календарю МСК.
Внизу — медианы по группам часа выхода. Данные — history/videos-ГГГГ-ММ.csv (строки src=rss — точные).
Точность зависит от частоты снимков: для «тишины» нужны снимки через 2–6–10 ч после выхода (строка @handle в request.txt)."""
import csv
import datetime as dt
import glob
import statistics
import sys
from collections import defaultdict

MSK = dt.timedelta(hours=3)
AGES = (6, 12, 24, 48, 96)
DOW = "пн вт ср чт пт сб вс".split()


def load(handle):
    pts, pub, title = defaultdict(set), {}, {}
    for f in sorted(glob.glob("history/videos-*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r["handle"] != handle or r["src"] != "rss" or not r["published_utc"]:
                continue
            try:
                c = dt.datetime.strptime(r["checked_utc"], "%Y-%m-%d %H:%M")
                p = dt.datetime.fromisoformat(r["published_utc"][:16])
            except ValueError:
                continue
            pub[r["video_id"]], title[r["video_id"]] = p, r["title"]
            pts[r["video_id"]].add((c, int(r["views"])))
    return pts, pub, title


def at(s, p, t):
    """Просмотры в момент t (UTC) по снимкам s; None, если ближайшие снимки дальше 40% возраста."""
    prev = (p, 0)
    for c, n in s:
        if c >= t:
            age = (t - p).total_seconds()
            if (c - t).total_seconds() > 0.4 * age and (t - prev[0]).total_seconds() > 0.4 * age:
                return None
            span = (c - prev[0]).total_seconds()
            return round(prev[1] + (n - prev[1]) * ((t - prev[0]).total_seconds() / span)) if span else n
        prev = (c, n)
    return None


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    handle = a[0]
    since = dt.datetime.fromisoformat(a[a.index("--since") + 1]) if "--since" in a else dt.datetime(2000, 1, 1)
    pts, pub, title = load(handle)
    groups = defaultdict(list)
    print(f"{'выход МСК':16} {'id':12} " + " ".join(f"{h:>5}ч" for h in AGES) + "   тишина      день0/день1  название")
    for v in sorted(pub, key=pub.get):
        if pub[v] < since or ("--long" in a and "#shorts" in title[v].lower()):
            continue
        s, p = sorted(pts[v]), pub[v]
        vals = [at(s, p, p + dt.timedelta(hours=h)) for h in AGES]
        lo = max([(c - p).total_seconds() / 3600 for c, n in s if n < 20] or [0])
        hi = min([(c - p).total_seconds() / 3600 for c, n in s if n >= 20] or [0])
        quiet = f"{lo:4.1f}–{hi:4.1f}ч" if hi else "   —     "
        d0 = (p + MSK).replace(hour=0, minute=0) - MSK
        e0, e1 = at(s, p, d0 + dt.timedelta(days=1)), at(s, p, d0 + dt.timedelta(days=2))
        days = f"{e0 if e0 is not None else '—'}/{(e1 - e0) if None not in (e0, e1) else '—'}"
        loc = p + MSK
        print(f"{DOW[loc.weekday()]} {loc:%d.%m %H:%M}  {v:12} " + " ".join(f"{x if x is not None else '—':>6}" for x in vals)
              + f"   {quiet}  {days:>11}  {title[v][:45]}")
        key = "утро (до 12:00)" if loc.hour < 12 else "день (12–17)" if loc.hour < 17 else "вечер (17+)"
        groups[key].append(vals)
    print("\nМедианы по часу выхода (только ролики, где есть значение):")
    for k, rows in groups.items():
        med = []
        for i in range(len(AGES)):
            xs = [r[i] for r in rows if r[i] is not None]
            med.append(f"{round(statistics.median(xs)) if xs else '—':>6}({len(xs)})")
        print(f"  {k:16} " + " ".join(med))


if __name__ == "__main__":
    main()
