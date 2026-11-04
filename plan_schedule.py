"""План на 30 дней: 90 роликов по 3 цитаты. python3 plan_schedule.py [seed] [дата старта YYYY-MM-DD]
Пишет schedule_30d.json (для бота) и schedule_30d.xlsx (для человека)."""
import datetime as dt
import json
import random
import sys
from pathlib import Path

import quotecard as qc
from orchestra import ORCH
from quotes_bank import QUOTES

HERE = Path(__file__).parent
DAYS, PER_DAY = 30, 3
TIMES = ["09:00", "14:00", "19:00"]
DARK = {"night", "cabin", "aurora", "moon_sea", "candle", "rain_window"}
HASHTAGS = "#цитаты #мудрость #цитатыизкниг #quotes #wisdom #watercolor #shorts"


def author_key(d):
    return d["author_en"].split("  ·  ")[0].strip()


def first_line(d):
    s = d["ru"] if isinstance(d["ru"], str) else " ".join(d["ru"])
    s = s.strip().rstrip(".!…")
    if len(s) > 60:
        s = s[:57].rsplit(" ", 1)[0] + "…"
    return s


def make_title(qids, k, limit=100):
    d = QUOTES[qids[0]]
    a = author_key(d)
    a_short = a.split()[-1] if len(a) > 16 and " " in a else a
    suffixes = [f" ✨ {a} + 2 more #shorts", f" 🤍 Три мысли на сегодня | {a_short} #shorts", f" ✨ Words to keep | {a} #shorts"]
    suf = suffixes[k % 3]
    s = d["ru"] if isinstance(d["ru"], str) else " ".join(d["ru"])
    s = s.strip().rstrip(".!…")
    room = limit - len(suf)
    if len(s) > room:
        s = s[:room - 1].rsplit(" ", 1)[0].rstrip(",;:— ") + "…"
    return s + suf


def make_description(qids):
    names_ru = " · ".join(QUOTES[q]["author_ru"].split("  ·  ")[0] for q in qids)
    names_en = " · ".join(author_key(QUOTES[q]) for q in qids)
    return (f"Три мысли классиков на акварели: {names_ru}.\nThree timeless thoughts on watercolor: {names_en}.\n"
            f"Русский текст и английский перевод.\n\n{HASHTAGS}")


def plan(seed=1, start=None):
    rnd = random.Random(seed)
    qids = list(QUOTES)
    rnd.shuffle(qids)
    scenes_all = list(qc.SCENES)
    styles = list(ORCH)
    videos = []
    used_q = set()
    recent_scenes = []
    style_i = 0
    day_styles = []
    start = start or dt.date.today() + dt.timedelta(days=1)
    for day in range(DAYS):
        day_styles = []
        for slot in range(PER_DAY):
            # --- 3 цитаты: разные авторы, не более одной пословицы
            picked = []
            for q_ in qids:
                if q_ in used_q:
                    continue
                d = QUOTES[q_]
                a = author_key(d)
                if any(author_key(QUOTES[p]) == a for p in picked):
                    continue
                if "proverb" in a.lower() and any("proverb" in author_key(QUOTES[p]).lower() for p in picked):
                    continue
                picked.append(q_)
                if len(picked) == 3:
                    break
            if len(picked) < 3:  # банк кончился — начинаем заново
                used_q = set()
                return plan(seed + 1, start)
            used_q.update(picked)
            # короткая цитата первой — она же в названии
            picked.sort(key=lambda q_: len(QUOTES[q_]["ru"] if isinstance(QUOTES[q_]["ru"], str) else " ".join(QUOTES[q_]["ru"])))
            # --- сцены: не из последних 9, светлым цитатам — не тёмные
            scenes = []
            for q_ in picked:
                mood = QUOTES[q_]["mood"]
                cand = [s for s in scenes_all if s not in scenes and s not in recent_scenes[-9:]]
                if mood == "light":
                    cand = [s for s in cand if s not in DARK] or cand
                elif mood == "dark":
                    cand = [s for s in cand if s in DARK] or cand
                if not cand:
                    cand = [s for s in scenes_all if s not in scenes]
                s = rnd.choice(cand)
                scenes.append(s)
                recent_scenes.append(s)
            # --- музыка: в день три разных стиля, по кругу
            while True:
                st = styles[style_i % len(styles)]
                style_i += 1
                if st not in day_styles:
                    break
            day_styles.append(st)
            n = len(videos) + 1
            date = start + dt.timedelta(days=day)
            videos.append(dict(
                n=n, day=day + 1, slot=slot + 1, date=date.isoformat(), time=TIMES[slot],
                quotes=picked, scenes=scenes, music=st, seed=1000 + n,
                title=make_title(picked, n), description=make_description(picked),
                name=f"d{day + 1:02d}_{slot + 1}",
            ))
    return videos


def write_xlsx(videos, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "План 30 дней"
    head = ["День", "Дата", "Время", "Ролик", "Цитата 1", "Автор 1", "Сцена 1", "Цитата 2", "Автор 2", "Сцена 2",
            "Цитата 3", "Автор 3", "Сцена 3", "Музыка", "Название для YouTube"]
    ws.append(head)
    for c in range(1, len(head) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
        ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor="EDE7DC")
    scene_ru = {"sunrise": "рассвет над водой", "winter": "зимнее поле", "night": "ночные горы", "meadow": "луг с тропинкой", "sea": "море, парусник",
                "autumn": "осенняя аллея", "sakura": "сакура у пруда", "lavender": "лаванда", "alpine": "альпийское озеро", "lighthouse": "маяк",
                "balloons": "воздушные шары", "cabin": "зимняя изба", "aurora": "северное сияние", "birch": "берёзы", "sunflowers": "подсолнухи",
                "moon_sea": "луна над морем", "rain_window": "дождь за окном", "windmill": "мельница, тюльпаны", "dunes": "дюны", "forest_rays": "лес в тумане",
                "waterfall": "водопад", "deer": "олень в снегу", "lotus": "лотосы", "wheat": "пшеница и дуб", "savanna": "саванна", "swans": "лебеди",
                "candle": "свеча и книга", "beach": "тропический пляж"}
    music_ru = {"orch_dawn": "Рассвет", "orch_hope": "Надежда", "orch_cello": "Виолончель", "orch_night": "Ночь", "orch_sea": "Море",
                "orch_winter": "Зима", "orch_horns": "Валторны", "orch_lullaby": "Колыбельная", "orch_dorian": "Дорийский", "orch_lydian": "Лидийский"}
    for v in videos:
        row = [v["day"], v["date"], v["time"], v["name"]]
        for q_, s in zip(v["quotes"], v["scenes"]):
            d = QUOTES[q_]
            txt = d["ru"] if isinstance(d["ru"], str) else " ".join(d["ru"])
            row += [txt, d["author_ru"].replace("  ·  ", " · "), scene_ru.get(s, s)]
        row += [music_ru.get(v["music"], v["music"]), v["title"]]
        ws.append(row)
    widths = [6, 11, 7, 8, 44, 26, 18, 44, 26, 18, 44, 26, 18, 12, 50]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "E2"
    wb.save(path)


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    start = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    videos = plan(seed, start)
    (HERE / "schedule_30d.json").write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    write_xlsx(videos, HERE / "schedule_30d.xlsx")
    used = {q_ for v in videos for q_ in v["quotes"]}
    from collections import Counter
    sc = Counter(s for v in videos for s in v["scenes"])
    print(f"роликов {len(videos)}, цитат использовано {len(used)} из {len(QUOTES)}, сцен: {len(sc)} (мин {min(sc.values())}, макс {max(sc.values())})")
    for v in videos[:6]:
        print(v["name"], v["time"], v["quotes"], v["scenes"], v["music"])
