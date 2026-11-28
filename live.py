"""«Почему так?» — живые кадры вместо значка (гипотеза H49, «да» Михаила 27.11.2026).

В выбранные часы (config.json: live_hours, по МСК, до даты live_until) ролик собирается так:
фон — настоящие видеоклипы по теме сценария, на кадре — подпись 2–4 слова (caps из банка),
голос, музыка и звуковые акценты — как в виде v2.
Откуда клипы (28.11.2026: Pexels перестал выдавать новые ключи — «New API key issuance is currently paused»):
  PIXABAY_API_KEY в .env — Pixabay (бесплатная лицензия Pixabay, коммерческое использование без указания автора;
                           вертикальных клипов мало — горизонтальные обрезаются по центру до 9:16);
  PEXELS_API_KEY  в .env — Pexels (если ключ когда-нибудь появится; берётся, только когда нет ключа Pixabay).
Нет ключа, нет клипов или любая ошибка — make_video.build делает обычный вид v2.

Проверка ключа на сервере:  python3 live.py --check
"""
import datetime as dt
import hashlib
import json
import os
import random
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

import make_video as mv

W, H, FPS = mv.W, mv.H, mv.FPS
MSK = dt.timezone(dt.timedelta(hours=3))

# слова из поля stock банка -> запрос для поиска клипов (по-английски находит намного больше)
EN = {
    "аккумулятор": "battery", "акула": "shark", "аптека": "pharmacy", "атом": "science laboratory",
    "банка": "glass jar", "бензин": "gas station", "богомол": "praying mantis", "верблюд": "camel",
    "взрыв": "fireworks", "вирус": "microscope", "вода": "water", "водител": "driving car",
    "водитель": "driving car", "волк": "wolf", "волн": "ocean waves", "волна": "ocean waves",
    "волосы": "hair", "время": "clock", "вулкан": "volcano", "газ": "gas stove", "гараж": "garage",
    "глаз": "eye close up", "глубина": "deep sea", "гнездо": "bird nest", "гора": "mountains",
    "горяч": "boiling water", "гриб": "mushroom forest", "гроза": "thunderstorm", "гусеница": "caterpillar",
    "дерево": "tree", "дом": "house", "дорога": "road", "дыра": "space", "еда": "food",
    "жар": "fire", "желудок": "eating", "животные": "wild animals", "жук": "beetle", "звезда": "stars night sky",
    "звезды": "stars night sky", "звук": "sound speaker", "земля": "planet earth", "золото": "gold",
    "зрение": "eye", "искры": "sparks", "камень": "stones", "картошка": "potato", "кит": "whale",
    "клетка": "microscope", "клетки": "microscope", "книга": "reading book", "кожа": "skin care",
    "колибри": "hummingbird", "колокол": "bell", "корабль": "ship", "космос": "space",
    "кость": "x-ray", "кровь": "doctor", "курица": "chicken", "лава": "lava", "лекарство": "pills",
    "лес": "forest", "лиса": "fox", "лицо": "face", "лодка": "boat", "лось": "moose", "луна": "moon",
    "лёд": "ice", "машин": "cars traffic", "машина": "car", "медведь": "bear", "металл": "metal",
    "метеорит": "meteor", "минуты": "clock", "мозг": "brain", "молния": "lightning", "море": "sea",
    "мороз": "frost", "мотор": "car engine", "муравей": "ants", "мёд": "honey", "напиток": "drink",
    "насекомые": "insects", "нос": "nose", "ночь": "night city", "обезьяна": "monkey", "огонь": "fire",
    "океан": "ocean", "пар": "steam", "паук": "spider", "пламя": "flame", "планета": "planet",
    "поезд": "train", "позвоночник": "back pain", "полёт": "airplane flight", "птица": "bird",
    "птицы": "birds", "пустыня": "desert", "пчела": "bee", "радиатор": "radiator",
    "радиоактивный": "nuclear power plant", "ракета": "rocket launch", "рана": "bandage",
    "растение": "plant", "рост": "growing plant", "рыба": "fish", "самолёт": "airplane", "сахар": "sugar",
    "свеча": "candle", "сердце": "heartbeat", "скелет": "x-ray", "снег": "snow", "собака": "dog",
    "солнце": "sun", "сон": "sleeping", "сосуды": "doctor", "таблетки": "pills", "тело": "human body",
    "ток": "electricity", "тормоз": "car brakes", "утка": "duck", "ухо": "ear", "физика": "science",
    "химик": "chemistry lab", "химия": "chemistry lab", "хлеб": "bread", "холод": "cold winter",
    "цветы": "flowers", "часы": "clock", "человек": "people walking", "чёрная": "black hole",
    "электричество": "electricity", "яд": "snake", "ёж": "hedgehog", "смерть": "",
}

ACCENT_CAPS = ("это миф", "это правда", "правда", "миф", "не всегда", "правда наполовину")


def now_msk():
    return dt.datetime.now(MSK)


def want(cfg, now=None):
    """Живой вид нужен в этот запуск? (час по МСК из live_hours; за 15 мин до часа — тоже)."""
    if os.environ.get("LIVE_FORCE") == "1":
        return True
    hours = cfg.get("live_hours") or []
    if not hours:
        return False
    now = now or now_msk()
    until = cfg.get("live_until")
    if until and now.date() > dt.date.fromisoformat(until):
        return False
    nxt = now + dt.timedelta(minutes=15)
    return now.hour in hours or (nxt.hour in hours and nxt.hour != now.hour)


def queries(script):
    """Запросы для поиска клипов: stock_en из сценария, если есть, иначе перевод слов поля stock (без повторов)."""
    if script.get("stock_en"):
        q = script["stock_en"]
        return [x.strip() for x in (q if isinstance(q, list) else q.split("|")) if x.strip()]
    out = []
    for w in (script.get("stock") or "").split():
        e = EN.get(w.lower().strip(",."))
        if e and e not in out:
            out.append(e)
    return out


def _get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; pochemu-live)", **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def provider():
    """('pixabay'|'pexels', ключ) — Pixabay главный (Pexels с 28.11.2026 новых ключей не выдаёт)."""
    if os.environ.get("PIXABAY_API_KEY"):
        return "pixabay", os.environ["PIXABAY_API_KEY"]
    if os.environ.get("PEXELS_API_KEY"):
        return "pexels", os.environ["PEXELS_API_KEY"]
    return None, None


def search(query, key, per_page=15, src="pixabay"):
    """Список клипов в общем виде: {id, duration, w, h, link}; только mp4, меньшая сторона ≥720, большая ≤3840."""
    out = []
    if src == "pixabay":
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
            {"key": key, "q": query[:100], "video_type": "film", "safesearch": "true",
             "per_page": max(3, min(per_page * 2, 200))})
        with _get(url, timeout=30) as r:
            hits = json.load(r).get("hits", [])
        for v in hits:
            vs = [f for f in (v.get("videos") or {}).values()
                  if isinstance(f, dict) and f.get("url") and f.get("width") and f.get("height")]
            vs = [f for f in vs if 720 <= min(f["width"], f["height"]) and max(f["width"], f["height"]) <= 3840]
            if not vs:
                continue
            # кадр 1080×1920: вертикальному нужна высота ~1920, горизонтальному — ~1080 (дальше режем по центру)
            f = min(vs, key=lambda f: (abs(f["height"] - (1920 if f["height"] >= f["width"] else 1080)),
                                      f["width"] * f["height"]))
            out.append({"id": f"pb{v.get('id')}", "duration": v.get("duration", 0),
                        "w": f["width"], "h": f["height"], "link": f["url"]})
        out.sort(key=lambda c: c["h"] < c["w"])          # вертикальные — первыми
        return out
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "size": "medium", "per_page": per_page})
    with _get(url, {"Authorization": key}, 30) as r:
        vids = json.load(r).get("videos", [])
    for v in vids:
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                 and f.get("height") and f.get("width") and f["height"] >= f["width"] and 960 <= f["height"] <= 2160]
        if files:
            f = min(files, key=lambda f: abs(f["height"] - 1920))
            out.append({"id": f"px{v.get('id')}", "duration": v.get("duration", 0),
                        "w": f["width"], "h": f["height"], "link": f["link"]})
    return out


def fetch_clips(qs, n, work, rnd, log=print):
    """До n разных клипов: по очереди из каждого запроса, чтобы соседние сцены отличались."""
    src, key = provider()
    if not key:
        raise RuntimeError("нет ключа PIXABAY_API_KEY (или PEXELS_API_KEY) в .env")
    pools = []
    for q in qs[:4]:
        vids = [v for v in search(q, key, src=src) if v.get("duration", 0) >= 4]
        top = [v for v in vids if v["h"] >= v["w"]]      # вертикальные — в начале пула, остальные — вперемешку за ними
        rest = [v for v in vids if v["h"] < v["w"]]
        rnd.shuffle(top)
        rnd.shuffle(rest)
        vids = top + rest
        if vids:
            pools.append((q, vids))
        log(f"{src} «{q}»: {len(vids)} подходящих (вертикальных {len(top)})")
    out, seen, k = [], set(), 0
    while len(out) < n and any(p[1] for p in pools):
        q, vids = pools[k % len(pools)]
        k += 1
        if not vids:
            continue
        v = vids.pop(0)
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        dest = work / f"live{len(out)}.mp4"
        try:
            with _get(v["link"], timeout=120) as r, open(dest, "wb") as o:
                shutil.copyfileobj(r, o)
            if mv.duration(dest) < 3:
                continue
        except Exception as e:  # noqa: BLE001 — один клип не скачался, берём следующий
            log(f"клип не скачался: {e}")
            continue
        out.append(dest)
    if len(out) < 2:
        raise RuntimeError(f"мало живых клипов ({len(out)}) по запросам {qs}")
    return out


# ---------- подписи ----------

def _text_block(d, text, size, cx, cy, fill, max_w, stroke=7, gap=22):
    """Текст по центру; шрифт уменьшается, пока не влезет в 3 строки."""
    for sz in (size, int(size * 0.9), int(size * 0.8), int(size * 0.7)):
        fnt = mv.font(sz)
        lines = mv.wrap(d, text, fnt, max_w)
        if len(lines) <= 3:
            break
    lines = lines[:3]
    hs = [fnt.getbbox(l)[3] - fnt.getbbox(l)[1] for l in lines]
    total = sum(hs) + gap * (len(lines) - 1)
    y = cy - total / 2
    for l, h in zip(lines, hs):
        tw = d.textlength(l, font=fnt)
        d.text((cx - tw / 2, y - fnt.getbbox(l)[1]), l, font=fnt, fill=fill,
               stroke_width=stroke, stroke_fill=(0, 0, 0, 235))
        y += h + gap
    return total


def overlay(kind, text, handle, path, accent=(255, 211, 77)):
    """Прозрачный слой 1080×1920: крючок сверху, подпись 2–4 слова над зоной кнопок Shorts, концовка ДА/НЕТ."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if handle:
        f = mv.font(34)
        tw = d.textlength(handle, font=f)
        d.text(((W - tw) / 2, 120), handle, font=f, fill=(255, 255, 255, 170), stroke_width=2, stroke_fill=(0, 0, 0, 140))
    if kind == "hook":
        _text_block(d, text, 86, W / 2, H * 0.30, (255, 255, 255, 255), 920)
    elif kind == "body":
        if text:
            col = accent + (255,) if text.strip().lower() in ACCENT_CAPS else (255, 255, 255, 255)
            _text_block(d, text, 92, W / 2, H * 0.64, col, 940)
    else:  # cta
        _text_block(d, text, 96, W / 2, H * 0.40, (255, 255, 255, 255), 940)
        f = mv.font(70)
        for lab, x, bg in (("ДА", W / 2 - 170, (52, 168, 83, 235)), ("НЕТ", W / 2 + 170, (220, 60, 60, 235))):
            tw = d.textlength(lab, font=f)
            d.rounded_rectangle([x - tw / 2 - 46, H * 0.52 - 58, x + tw / 2 + 46, H * 0.52 + 58], radius=30, fill=bg)
            d.text((x - tw / 2, H * 0.52 - 58 + (116 - (f.getbbox(lab)[3] + f.getbbox(lab)[1])) / 2), lab, font=f, fill=(255, 255, 255, 255))
        f2 = mv.font(44)
        s = "пиши в комментариях"
        tw = d.textlength(s, font=f2)
        d.text(((W - tw) / 2, H * 0.52 + 100), s, font=f2, fill=(255, 255, 255, 230), stroke_width=4, stroke_fill=(0, 0, 0, 200))
    img.save(path)


# ---------- сборка ----------

def build_live(script, cfg, out_path, work_dir, tts=None, log=print):
    tts = tts or mv.speak
    work = Path(work_dir)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rnd = random.Random(int(hashlib.md5(script["title"].encode()).hexdigest(), 16))
    voices = cfg.get("voices") or ["ru-RU-DmitryNeural"]
    voice = rnd.choice(voices)
    lines = [l for l in script["lines"] if l.strip()][:cfg.get("max_lines", mv.MAX_LINES_V2)]
    total = len(lines) + 1                               # + концовка «А ты это знал?»
    qs = queries(script)
    log(f"Живые кадры (H49): запросы {qs}, фраз {len(lines)}, голос {voice}")
    if not qs:
        raise RuntimeError("у сценария нет слов для поиска клипов")
    clips = fetch_clips(qs, min(4, total), work, rnd, log)   # клипы до озвучки: нет клипов — сразу обычный вид

    rate = cfg.get("voice_rate_v2", "+8%")
    durs, audios = [], []
    for i, line in enumerate(lines):
        mp3 = work / f"a{i:02d}.mp3"
        tts(line, voice, rate, mp3)
        durs.append(mv.duration(mp3) + (0.45 if i == 0 else mv.PAUSE))
        audios.append(mp3)
    cta_mp3 = work / "cta.mp3"
    tts(mv.CTA_TEXT, voice, rate, cta_mp3)
    durs.append(mv.duration(cta_mp3) + 1.3)
    audios.append(cta_mp3)
    total_dur = sum(durs)

    caps = script.get("caps") or []
    seg_list = work / "segments.txt"
    with open(seg_list, "w") as sl:
        for i in range(total):
            dur = durs[i]
            kind = "hook" if i == 0 else ("cta" if i == total - 1 else "body")
            if kind == "hook":
                text = script["title"]            # на кадре — короткий вопрос-название, голос читает первую фразу
            elif kind == "cta":
                text = mv.CTA_TEXT
            else:
                text = caps[i] if i < len(caps) and caps[i] else ""
            txt = work / f"t{i:02d}.png"
            overlay(kind, text, cfg.get("channel_handle", ""), txt)
            clip = clips[i % len(clips)]
            cd = mv.duration(clip)
            ss = rnd.uniform(0, max(cd - dur - 0.3, 0)) if i else 0.0
            dim = "-0.10" if kind == "cta" else "-0.04"
            pop = "" if i == 0 else ",fade=t=in:st=0:d=0.15:alpha=1"
            filt = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                    f"eq=brightness={dim}:saturation=1.06,setsar=1[bg];"
                    f"[1:v]format=rgba{pop}[tx];[bg][tx]overlay=0:0:shortest=1[v]")
            seg = work / f"s{i:02d}.mp4"
            mv.run(["ffmpeg", "-y", "-ss", f"{ss:.2f}", "-stream_loop", "-1", "-i", clip,
                    "-loop", "1", "-framerate", FPS, "-i", txt,
                    "-filter_complex", filt, "-map", "[v]", "-t", f"{dur:.3f}", "-an", *mv.X264, seg])
            sl.write(f"file '{seg.name}'\n")

    # голос целиком (как в v2)
    ins, parts = [], []
    for i, a in enumerate(audios):
        pad = 0.45 if i == 0 else (1.3 if i == total - 1 else mv.PAUSE)
        ins += ["-i", a]
        parts.append(f"[{i}:a]aresample=44100,apad=pad_dur={pad}[s{i}]")
    parts.append("".join(f"[s{i}]" for i in range(total)) + f"concat=n={total}:v=0:a=1[voice]")
    voice_f = work / "voice.m4a"
    mv.run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(parts), "-map", "[voice]", "-c:a", "aac", "-b:a", "160k", voice_f])

    # звуковые акценты (как в v2)
    sfx_plan = []
    if cfg.get("sfx", True):
        try:
            import sfx as SFX
            starts = [sum(durs[:i]) for i in range(total)]
            sfx_plan.append(("whoosh", 0.0, 0.9))
            for i in range(1, total):
                if i == total - 1:
                    k = "ding"
                elif i == 1:
                    low = lines[1].lower()
                    k = "buzz" if "миф" in low else ("ding" if "правда" in low else SFX.for_format(script.get("format")))
                else:
                    k = "tick"
                sfx_plan.append((k, max(0.0, starts[i] - 0.05), 0.7 if k != "tick" else 0.5))
            for j, (k, _, _) in enumerate(sfx_plan):
                SFX.make(k, work / f"sfx{j:02d}.wav")
        except Exception as e:  # noqa: BLE001
            log(f"звуковые акценты: {e}")
            sfx_plan = []

    music_files = sorted((mv.BASE / "music").glob("*.mp3")) if (mv.BASE / "music").exists() else []
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", seg_list, "-i", voice_f]
    chains, mix, nin = [], ["[1:a]"], 2
    if music_files:
        want_m = (cfg.get("music_by_format") or {}).get(script.get("format") or "", [])
        fit = [f for f in music_files if f.name in want_m]
        m = rnd.choice(fit or music_files)
        cmd += ["-stream_loop", "-1", "-i", m]
        chains.append(f"[{nin}:a]volume={cfg.get('music_volume', 0.08)},afade=t=out:st={max(total_dur - 1.5, 0):.2f}:d=1.5[m]")
        mix.append("[m]")
        nin += 1
    for j, (k, at, vol) in enumerate(sfx_plan):
        cmd += ["-i", work / f"sfx{j:02d}.wav"]
        ms = int(at * 1000)
        chains.append(f"[{nin}:a]aformat=sample_rates=44100:channel_layouts=mono,adelay={ms}|{ms},volume={vol * cfg.get('sfx_volume', 0.35):.2f}[x{j}]")
        mix.append(f"[x{j}]")
        nin += 1
    if len(mix) > 1:
        chains.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0[a]")
        cmd += ["-filter_complex", ";".join(chains), "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total_dur:.3f}", "-movflags", "+faststart", out_path]
    mv.run(cmd)
    log(f"Живые кадры: {len(clips)} клипа ({provider()[0]}), {total_dur:.1f} с")
    return total_dur


def check():
    """Для команды обновления: есть ли ключ и отвечает ли источник клипов."""
    env = mv.BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            for name in ("PIXABAY_API_KEY", "PEXELS_API_KEY"):
                if line.strip().startswith(name + "=") and not os.environ.get(name):
                    os.environ[name] = line.split("=", 1)[1].strip().strip('"').strip("'")
    src, key = provider()
    if not key:
        print("КЛЮЧА НЕТ")
        return 3
    name = "PIXABAY" if src == "pixabay" else "PEXELS"
    try:
        vids = search("ice lake", key, 10, src)
    except Exception as e:  # noqa: BLE001
        print(f"{name} НЕ ОТВЕЧАЕТ: {e}")
        return 4
    vert = sum(1 for v in vids if v["h"] >= v["w"])
    print(f"{name} ОК: по запросу «ice lake» {len(vids)} клипов (вертикальных {vert}, остальные обрежу по центру)")
    return 0 if vids else 4


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
