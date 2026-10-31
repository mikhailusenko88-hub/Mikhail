"""Сборка вертикального клипа: сценарий -> озвучка -> сцены (новый фон на каждой фразе) -> mp4."""
import asyncio
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
PAUSE = 0.3          # пауза после фразы, сек
BASE = Path(__file__).resolve().parent
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS)]

FONT_CANDIDATES = [
    BASE / "fonts" / "Montserrat-Bold.ttf",
    Path("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf"),
    Path("/usr/share/fonts/truetype/roboto/hinted/Roboto-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

PALETTES = [
    ((22, 34, 64), (64, 96, 170), (255, 196, 64)),
    ((30, 22, 48), (120, 60, 140), (255, 140, 180)),
    ((14, 46, 44), (30, 130, 110), (250, 220, 120)),
    ((48, 24, 18), (170, 80, 50), (255, 220, 150)),
    ((20, 20, 24), (70, 76, 92), (120, 220, 255)),
    ((18, 40, 24), (60, 120, 70), (200, 255, 140)),
]
FORMAT_ICONS = {"Факт дня": "★", "Миф или правда": "?!", "Топ-3": "№",
                "Как это работает": "⚙", "Загадка": "?",
                "Білесің бе?": "★", "Аңыз ба, шындық па?": "?!", "Қазақша сөз": "Aa",
                "Мақал-мәтел": "❝", "Қай қала?": "?"}


def font(size):
    for p in FONT_CANDIDATES:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    raise RuntimeError("Не найден шрифт: установите fonts-dejavu-core")


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg/ffprobe упал:\n{r.stderr[-1500:]}")
    return r.stdout


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", path]).strip())


# ---------- озвучка (edge-tts, бесплатно) ----------

async def _tts(text, voice, rate, path):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=rate).save(str(path)), timeout=40)


def _try(text, voice, rate, path):
    try:
        if path.exists():
            path.unlink()
        asyncio.run(_tts(text, voice, rate, path))
        return path.exists() and path.stat().st_size > 1000
    except Exception:
        return False


def _split(text):
    """Режем фразу пополам по запятой/тире/пробелу ближе к середине."""
    mid = len(text) // 2
    cuts = [i for i, ch in enumerate(text) if ch in ",—–:;"] or \
           [i for i, ch in enumerate(text) if ch == " "]
    if not cuts:
        return [text]
    i = min(cuts, key=lambda c: abs(c - mid))
    left, right = text[:i + 1].strip(" ,"), text[i + 1:].strip(" ,")
    return [p for p in (left, right) if p]


def speak(text, voice, rate, path, tries=3):
    """edge-tts иногда отвечает «No audio was received» на отдельные фразы.
    Порядок: тот же голос (с паузами) -> другой голос -> фраза по частям."""
    import time
    if voice.startswith("kk-KZ"):
        alt = "kk-KZ-AigulNeural" if "Daulet" in voice else "kk-KZ-DauletNeural"
    else:
        alt = "ru-RU-SvetlanaNeural" if "Dmitry" in voice else "ru-RU-DmitryNeural"
    for k in range(tries):
        if _try(text, voice, rate, path):
            time.sleep(0.5)
            return
        time.sleep(3 + 3 * k)
    if _try(text, alt, "+0%", path):
        return
    parts = _split(text)
    if len(parts) > 1:
        files = []
        for j, p in enumerate(parts):
            pf = path.with_name(f"{path.stem}_p{j}.mp3")
            if not (_try(p, voice, rate, pf) or _try(p, alt, "+0%", pf)):
                break
            files.append(pf)
        else:
            lst = path.with_suffix(".txt")
            lst.write_text("".join(f"file '{f.name}'\n" for f in files))
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame",
                 "-b:a", "96k", path])
            return
    raise RuntimeError(f"Не удалось озвучить: {text!r}")


# ---------- фоновые видео Pexels (бесплатный ключ) ----------

def _get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "clips-bot", **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def stock_clips(query, n, work, rnd, log=print):
    """Скачивает до n разных вертикальных роликов по запросу. Возвращает список путей."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key or not query:
        return []
    try:
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": query, "orientation": "portrait", "size": "medium", "per_page": 30})
        data = json.load(_get(url, {"Authorization": key}, 30))
        vids = [v for v in data.get("videos", []) if v.get("duration", 0) >= 5]
        rnd.shuffle(vids)
        out = []
        for v in vids:
            files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4"
                     and f.get("height") and f.get("width") and f["height"] >= f["width"]
                     and 960 <= f["height"] <= 2160]
            if not files:
                continue
            f = min(files, key=lambda f: abs(f["height"] - 1920))
            dest = work / f"stock{len(out)}.mp4"
            with _get(f["link"], timeout=120) as r, open(dest, "wb") as o:
                shutil.copyfileobj(r, o)
            out.append(dest)
            if len(out) >= n:
                break
        if not out:
            log(f"Pexels: по запросу «{query}» нет вертикальных видео")
        return out
    except Exception as e:
        log(f"Pexels недоступен ({e}), рисую свой фон")
        return []


# ---------- графика ----------

def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def gradient(palette, rnd):
    top, bottom, accent = palette
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    for _ in range(5):
        r = rnd.randint(220, 480)
        x, y = rnd.randint(-100, W + 100), rnd.randint(200, H - 200)
        g.ellipse([x - r, y - r, x + r, y + r], fill=accent + (rnd.randint(18, 40),))
    return Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(90)))


def text_layer(accent, style, fmt, title, text, idx, total, handle, path, sub=None, title_sub=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    dark = (20, 20, 24)

    tf = font(50)
    tlines = wrap(d, title.upper(), tf, W - 220)[:3]
    lh = 62
    stf = font(34)
    stlines = wrap(d, title_sub, stf, W - 220)[:2] if title_sub else []
    box_h = lh * len(tlines) + 54 + (44 * len(stlines) + 6 if stlines else 0)
    head_y = 230 if style["title_top"] else H - 540 - box_h
    if fmt:
        bf = font(36)
        label = f"{FORMAT_ICONS.get(fmt, '•')}  {fmt.upper()}"
        lw = d.textlength(label, font=bf)
        bx = (W - lw) / 2 - 30
        d.rounded_rectangle([bx, head_y - 86, bx + lw + 60, head_y - 22], radius=32, fill=(255, 255, 255, 240))
        d.text((bx + 30, head_y - 77), label, font=bf, fill=dark)
    d.rounded_rectangle([70, head_y, W - 70, head_y + box_h], radius=34, fill=accent + (255,))
    for i, ln in enumerate(tlines):
        tw = d.textlength(ln, font=tf)
        d.text(((W - tw) / 2, head_y + 27 + i * lh), ln, font=tf, fill=dark)
    for i, ln in enumerate(stlines):
        tw = d.textlength(ln, font=stf)
        d.text(((W - tw) / 2, head_y + 27 + len(tlines) * lh + 4 + i * 44), ln, font=stf, fill=(60, 60, 66))

    for size in (88, 80, 72, 64, 58):
        mf = font(size)
        mlines = wrap(d, text, mf, W - 180)
        bl = int(size * 1.25)
        sf = font(int(size * 0.62))
        slines = wrap(d, sub, sf, W - 180) if sub else []
        sbl = int(size * 0.62 * 1.25)
        if bl * len(mlines) + (sbl * len(slines) + 34 if slines else 0) <= 820:
            break
    block_h = bl * len(mlines) + (sbl * len(slines) + 34 if slines else 0)
    zone = (head_y + box_h + 40, H - 340) if style["title_top"] else (200, head_y - 130)
    cy = zone[0] + (zone[1] - zone[0] - block_h) / 2
    d.rounded_rectangle([50, cy - 48, W - 50, cy + block_h + 38], radius=40, fill=(0, 0, 0, 150))
    for i, ln in enumerate(mlines):
        tw = d.textlength(ln, font=mf)
        x = (W - tw) / 2 if style["center"] else 95
        y = cy + i * bl
        d.text((x + 3, y + 4), ln, font=mf, fill=(0, 0, 0, 180))
        d.text((x, y), ln, font=mf, fill=(255, 255, 255))
    for i, ln in enumerate(slines):
        tw = d.textlength(ln, font=sf)
        x = (W - tw) / 2 if style["center"] else 95
        y = cy + len(mlines) * bl + 34 + i * sbl
        d.text((x + 2, y + 3), ln, font=sf, fill=(0, 0, 0, 180))
        d.text((x, y), ln, font=sf, fill=accent + (255,))

    dot, gap = 18, 18
    sx = (W - (total * dot + (total - 1) * gap)) / 2
    for i in range(total):
        x = sx + i * (dot + gap)
        d.ellipse([x, H - 300, x + dot, H - 300 + dot],
                  fill=accent + (255,) if i <= idx else (255, 255, 255, 120))
    if handle:
        hf = font(40)
        hw = d.textlength(handle, font=hf)
        d.text(((W - hw) / 2 + 2, H - 228), handle, font=hf, fill=(0, 0, 0, 160))
        d.text(((W - hw) / 2, H - 230), handle, font=hf, fill=(255, 255, 255, 235))
    img.save(path)


# ---------- сборка ----------

def build(script, cfg, out_path, work_dir, tts=speak, log=print):
    work = Path(work_dir)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    rnd = random.Random(int(hashlib.md5(script["title"].encode()).hexdigest(), 16))
    style = {"title_top": rnd.random() < 0.7, "center": rnd.random() < 0.75}
    voices = cfg.get("voices") or ["ru-RU-DmitryNeural"]
    voice = rnd.choice(voices)
    base_pal = rnd.randrange(len(PALETTES))
    accent = PALETTES[base_pal][2]

    lines = script["lines"]
    total = len(lines)

    # 1) озвучка по фразам
    durs, audios = [], []
    for i, line in enumerate(lines):
        mp3 = work / f"a{i:02d}.mp3"
        tts(line, voice, cfg.get("voice_rate", "+0%"), mp3)
        durs.append(duration(mp3) + PAUSE)
        audios.append(mp3)
    total_dur = sum(durs)

    # 2) фоны: свои видео на каждую фразу или сменяющиеся градиенты
    clips = stock_clips(script.get("stock"), total, work, rnd, log) if cfg.get("use_stock_video") else []

    # 3) сцены
    seg_list = work / "segments.txt"
    start = 0.0
    with open(seg_list, "w") as sl:
        for i, line in enumerate(lines):
            dur = durs[i]
            txt = work / f"t{i:02d}.png"
            subs = script.get("ru") or []
            text_layer(accent, style, script.get("format"), script["title"], line, i, total,
                       cfg.get("channel_handle", ""), txt,
                       sub=subs[i] if i < len(subs) else None, title_sub=script.get("title_ru"))
            seg = work / f"s{i:02d}.mp4"
            if clips:
                clip = clips[i % len(clips)]
                cd = duration(clip)
                ss = max(0.0, rnd.uniform(0, max(cd - dur - 0.2, 0)))
                bg_in = ["-ss", f"{ss:.2f}", "-stream_loop", "-1", "-i", clip]
                bg_f = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                        f"fps={FPS},eq=brightness=-0.10:saturation=0.95,setsar=1[bg]")
            else:
                pal = PALETTES[(base_pal + i) % len(PALETTES)]
                bgimg = work / f"g{i:02d}.jpg"
                gradient((pal[0], pal[1], accent), random.Random(rnd.random())) \
                    .convert("RGB").resize((int(W * 1.15), int(H * 1.15))).save(bgimg, quality=92)
                bg_in = ["-loop", "1", "-framerate", str(FPS), "-i", bgimg]
                # медленный наезд + сдвиг, у каждой сцены своё направление
                sx, sy = rnd.choice([(1, 1), (-1, 1), (1, -1), (-1, -1)])
                bg_f = (f"[0:v]crop={W}:{H}:x='(iw-{W})/2+{sx}*(iw-{W})/2*t/{dur:.2f}*0.9':"
                        f"y='(ih-{H})/2+{sy}*(ih-{H})/2*t/{dur:.2f}*0.9',setsar=1[bg]")
            fade = "" if i == 0 else ",fade=t=in:st=0:d=0.22:alpha=1"  # первый кадр — сразу крючок
            filt = (bg_f + ";"
                    f"[1:v]format=rgba{fade}[tx];"
                    f"color=c=white@0.9:s={W}x12:r={FPS}[bar];"
                    f"[bg][tx]overlay=0:0:shortest=1[v1];"
                    f"[v1][bar]overlay=x='-w+W*(t+{start:.3f})/{total_dur:.3f}':y=H-90:shortest=1[v]")
            run(["ffmpeg", "-y", *bg_in, "-loop", "1", "-framerate", FPS, "-i", txt,
                 "-filter_complex", filt, "-map", "[v]", "-t", f"{dur:.3f}", "-an", *X264, seg])
            sl.write(f"file '{seg.name}'\n")
            start += dur

    # 4) голос целиком
    ins, parts = [], []
    for i, a in enumerate(audios):
        ins += ["-i", a]
        parts.append(f"[{i}:a]aresample=44100,apad=pad_dur={PAUSE}[s{i}]")
    parts.append("".join(f"[s{i}]" for i in range(total)) + f"concat=n={total}:v=0:a=1[voice]")
    voice_f = work / "voice.m4a"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(parts), "-map", "[voice]",
         "-c:a", "aac", "-b:a", "160k", voice_f])

    # 5) склейка + (необязательно) музыка из папки music/
    music_files = sorted((BASE / "music").glob("*.mp3")) if (BASE / "music").exists() else []
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", seg_list, "-i", voice_f]
    if music_files:
        # музыка по смыслу рубрики (config.json → music_by_format), иначе любая
        want = (cfg.get("music_by_format") or {}).get(script.get("format") or "", [])
        fit = [f for f in music_files if f.name in want]
        m = rnd.choice(fit or music_files)
        cmd += ["-stream_loop", "-1", "-i", m, "-filter_complex",
                f"[2:a]volume={cfg.get('music_volume', 0.08)},"
                f"afade=t=out:st={max(total_dur - 1.5, 0):.2f}:d=1.5[m];"
                f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total_dur:.3f}",
            "-movflags", "+faststart", out_path]
    run(cmd)
    return total_dur


# ---------- сценарий ----------

RULES = {
    "Факт дня": "один удивительный, но проверенный факт и простое объяснение, почему так",
    "Миф или правда": "популярное убеждение; вторая фраза — чёткий ответ «Это миф» или «Это правда», дальше объяснение",
    "Топ-3": "три коротких пункта: «Первый: ...», «Второй: ...», «Третий: ...»",
    "Как это работает": "простое объяснение явления или устройства, понятное школьнику",
    "Загадка": "загадка в первой фразе, вторая — «Подумайте секунду», третья — ответ, дальше пояснение",
}


def pick_rotation(cfg, n_done):
    formats = cfg.get("formats") or ["Факт дня"]
    subs = cfg.get("subtopics") or [cfg["topic"]]
    return formats[n_done % len(formats)], subs[(n_done * 3) % len(subs)]


def ai_script(cfg, used_titles, n_done):
    import anthropic
    fmt, sub = pick_rotation(cfg, n_done)
    recent = "\n".join(f"- {t}" for t in used_titles[-80:]) or "(пока нет)"
    prompt = f"""Придумай сценарий короткого вертикального ролика (VK Клипы / Shorts) на русском.
Канал: {cfg['topic']}. Тема сегодня: {sub}. Рубрика «{fmt}»: {RULES.get(fmt, '')}.
Только достоверные, общепризнанные научные факты. Если не уверен в цифре — не используй её.
Не повторяй уже вышедшие ролики:
{recent}

Первая фраза — крючок до 70 символов, который заставит досмотреть.
Всего 5–7 коротких фраз, каждая до 130 символов. Числа пиши словами. Озвучка 25–45 секунд.
Ответь только JSON:
{{"title": "заголовок до 45 символов", "lines": ["..."], "tags": ["3-4 тега без #"],
 "stock": "2-3 английских слова для поиска фонового видео, например 'octopus underwater'"}}"""
    msg = anthropic.Anthropic().messages.create(
        model=cfg.get("ai_model", "claude-sonnet-5-5"), max_tokens=1500,
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    lines = [l.strip() for l in data["lines"] if l.strip()]
    if not (4 <= len(lines) <= 8) or not data.get("title") or data["title"] in used_titles:
        raise ValueError("сценарий не прошёл проверку")
    return {"format": fmt, "title": data["title"].strip()[:70], "lines": lines,
            "tags": [t.strip("# ") for t in data.get("tags", [])][:4],
            "stock": data.get("stock", "")}


def bank_script(used_titles, n_done=0, cfg=None):
    """Берёт неиспользованный сценарий из банка, чередуя рубрики по кругу."""
    bank = json.loads((BASE / (cfg or {}).get("bank_file", "topics.json")).read_text(encoding="utf-8"))
    fresh = [s for s in bank if s["title"] not in used_titles] or bank
    formats = (cfg or {}).get("formats") or []
    if formats:  # только рубрики из config.json (остальные отключены)
        fresh = [s for s in fresh if s.get("format") in formats] or fresh
    if formats:
        want = formats[n_done % len(formats)]
        for s in fresh:
            if s.get("format") == want:
                return s
    return fresh[0]


def get_script(cfg, used_titles, n_done, log=print):
    if cfg.get("use_ai") and os.environ.get("ANTHROPIC_API_KEY"):
        for attempt in range(2):
            try:
                return ai_script(cfg, used_titles, n_done), "ai"
            except Exception as e:
                log(f"ИИ-сценарий, попытка {attempt + 1}: {e}")
        log("Беру сценарий из запасного банка")
    return bank_script(used_titles, n_done, cfg), "bank"


def caption(script, cfg, max_tags=6):
    """Подпись: заголовок + крючок + хэштеги.
    Первые два — сильные теги ниши (их YouTube показывает над названием),
    потом теги темы ролика, в конце — общий тег."""
    defaults = cfg.get("default_tags", [])
    order = defaults[:2] + list(script.get("tags", [])) + defaults[2:]
    tags = []
    for t in order:
        t = "#" + re.sub(r"[^\wА-Яа-яЁё]", "", t.replace(" ", ""))
        if len(t) > 2 and t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    if script.get("title_ru"):
        ru0 = (script.get("ru") or [""])[0]
        return (f"{script['title']} | {script['title_ru']}\n\n{script['lines'][0]}\n{ru0}\n\n"
                + " ".join(tags[:max_tags]))
    return f"{script['title']}\n\n{script['lines'][0]}\n\n" + " ".join(tags[:max_tags])
