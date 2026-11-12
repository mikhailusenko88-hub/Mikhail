#!/usr/bin/env python3
"""Добавляет в server.py службы multik-tts (голос «Альбина») режим «bot» для роликов «Почему так?».
Для «Мультиков» ничего не меняется: всё новое включается только запросом со "style": "bot".

Режим «bot» — разметка ударений как в пробнике, который выбрали 2 ноября («Альбина, мягкий тон»):
  • «+» только в словах из двух и больше гласных (в «мы», «по», «ни» — без ударения, как у silero-stress);
  • в словах с «ё» без «+» ставится «+ё» (иначе Альбина иногда тянет ударение на другой слог: «Озёр»);
  • вопрос без вопросительного слова («Летучие мыши слепые?») — подъём голоса на последнем слове.
Плюс адрес /mark?text=… — какой текст с ударениями пойдёт в голос (для лога бота).

  python3 patch_server.py /opt/multik-tts/server.py      (0 — готово или уже было, 2 — не подошёл файл)
"""
import re
import sys
from pathlib import Path

MARK = "# --- режим «bot» (pochemu-albina) ---"

BLOCK = MARK + r'''
_QW = {"почему", "зачем", "как", "что", "чего", "чем", "кто", "кого", "кому", "где", "куда", "откуда", "когда",
       "сколько", "какой", "какая", "какое", "какие", "каких", "каким", "чей", "чья", "чьё", "чьи", "ли", "разве",
       "неужели", "отчего", "почём", "каков", "какова", "сколь"}
_SENT = re.compile(r"[^.!?…]+[.!?…]*")
BOT_Q_PITCH = "x-high"  # старый способ (до 08.11 вечера): подъём через голос; сейчас не используется
BOT_Q_BASE = "low"
# Вопрос без вопросительного слова («А ты это знал?») — мелодия по живому образцу (Михаил выбрал 08.11, вариант 4):
# последнее слово чуть медленнее, перед ним голос проваливается на BOT_Q_LOW полутонов от средней высоты фразы,
# затем взлетает до BOT_Q_HIGH к самому концу, без спада. Делается в Praat (PSOLA), тембр не меняется.
BOT_Q_MELODY = True
BOT_Q_LOW, BOT_Q_HIGH, BOT_Q_PRE = -3.0, 6.5, 0.14


def _guess_stress(w):
    """Слово без «+» (ruaccent не знает или пропустил во фразе): спросить ruaccent одно слово,
    иначе — ударение на предпоследний гласный («Манцин+елла», «Кар+ибах», «обжиг+ает», «к+ожу»)."""
    try:
        r = acc.process_all(w)
        if "+" in r and r.replace("+", "").lower() == w.lower():
            return r
    except Exception:
        pass
    idx = [i for i, c in enumerate(w) if c in VOW]
    i = idx[-2] if len(idx) >= 2 else idx[-1]
    return w[:i] + "+" + w[i:]


# Слова из одного слога (11.11.2026, Михаил услышал «Ан ещё стоял» и «почти пить тысяч лет»): без «+» модель читает их
# как безударные — «о» превращается в «а», «я» и «е» — в «и» («он» → «ан», «пять» → «пить», «ток» → «так», «снег» → «сник»).
# Поэтому ударение ставим и на них, кроме служебных слов, которые в речи и правда безударны.
_CLIT = {"в", "во", "к", "ко", "с", "со", "у", "о", "об", "от", "до", "по", "за", "на", "над", "под", "из", "при", "про",
         "для", "без", "не", "ни", "же", "бы", "ли", "ль", "и", "а", "да"}
# Тире модель не слышит совсем: «Самое холодное место во Вселенной — на Земле» читалось без остановки.
# Одна пауза (<break>) на его месте не годится: голос перед ней падает, как перед точкой («Длина. До тридцати метров»),
# и ударение съезжает на первый слог. Запятая + пауза: голос остаётся «на весу», пауза ровно та, что задана (проба 12.11.2026).
BOT_DASH_MODE = os.environ.get("BOT_DASH_MODE", "commabreak")   # commabreak | comma | break | none
BOT_DASH_MS = int(os.environ.get("BOT_DASH_MS", "200"))         # пауза на тире, мс; двойное тире «——» — в полтора раза дольше
BOT_ASSIM = os.environ.get("BOT_ASSIM", "1") == "1"             # звонкость на стыке: «сбит» -> «збит», «с головы» -> «зголовы»


def _bot_part(w, first=True, lead=True):
    if sum(c in VOW for c in w) <= 1:
        low = w.replace("+", "").lower()
        clit = low in _CLIT or not first or not any(c in VOW for c in w)   # «-то», «-ка», «из-под» — вторая часть без ударения
        if len(low) == 1 and low in VOW and w.replace("+", "").isupper() and not lead:
            clit = False                   # «Витамин А»: заглавная буква посреди фразы — это название, а не союз
        if low == "что":
            clit = not lead                # «Что это?» — с ударением; «…, что он» (союз) — без
        if clit:
            return w.replace("+", "")
        if "+" in w:
            return w
        i = next(i for i, c in enumerate(w) if c in VOW)
        return w[:i] + "+" + w[i:]
    if "+" in w:
        return w
    if "ё" in w or "Ё" in w:
        i = w.lower().index("ё")
        return w[:i] + "+" + w[i:]           # «озёр» -> «оз+ёр»
    return _guess_stress(w)                  # без ударения Альбина угадывает и смазывает слово


def _bot_word(m):
    w = m.group(0)
    if "-" in w and "+" in w:
        return w                             # «чт+о-нибудь»: ударение уже есть у слова целиком
    prev = m.string[:m.start()].rstrip()[-1:]
    lead = prev in ("", ".", "!", "?", "…", "—", "–", ":", "«", "(")     # слово начинает фразу или её часть
    return "-".join(_bot_part(x, i == 0, lead) for i, x in enumerate(w.split("-")))


def _dash(s):
    """Тире -> пауза (см. BOT_DASH_MODE). «——» — пауза подольше: «В ней —— яд»."""
    def rep(m):
        ms = int(BOT_DASH_MS * (1.6 if len(m.group(1)) > 1 else 1))
        if BOT_DASH_MODE == "comma":
            return ", "
        if BOT_DASH_MODE == "commabreak":
            return f', <break time="{ms}ms"/> '
        if BOT_DASH_MODE == "break":
            return f' <break time="{ms}ms"/> '
        return m.group(0)
    return re.sub(r"\s*,?\s+([—–]{1,2})\s+", rep, s)


# Звонкость на стыке (12.11.2026). После глухого согласного Альбина оглушает и следующий звонкий: «был сбит» звучало «спит»,
# «с головы» — «с коловы», «сгорит» — «скорит», «растут гуще» — «растут куще» (по спектру: 12 из 32 таких стыков глухие,
# после гласных и звонких — ни одного). В живой речи наоборот: первый согласный озвончается. Пишем так, как звучит.
_VOICE = {"т": "д", "к": "г", "с": "з", "п": "б", "ш": "ж", "ф": "в", "х": "г"}
_NL = r"(?<![А-Яа-яЁё+\-])"          # не внутри слова


def _assim(s):
    if not BOT_ASSIM:
        return s
    s = re.sub(_NL + r"([сС])(?=[бгдз])", lambda m: "з" if m.group(1) == "с" else "З", s)              # сбит -> збит
    s = re.sub(_NL + r"([сС]) ([бгдзБГДЗ])",                                                          # с головы -> зголовы
               lambda m: ("з" if m.group(1) == "с" else "З") + m.group(2).lower(), s)
    # «В тебе…» в начале фразы: «в» перед глухой Альбина глотает («Тебе больше чужих клеток»); «ф» — слышно. В середине фразы
    # не трогаем: там предлог и так слышен, а отдельное «ф» удлиняет паузу перед собой (проба 12.11.2026).
    s = re.sub(_NL + r"В(?= [птксшфхцчщПТКСШФХЦЧЩ])", "Ф", s)
    s = re.sub(r"(?<=[аеёиоуыэюялмнрй])([ткспшфх])(?= [бгдзБГДЗ])", lambda m: _VOICE[m.group(1)], s)  # как бетон -> каг бетон
    return s



# Что подобрано на слух и не меняется (Михаил, 08.11.2026): концовка роликов и хвост вопроса, по которому идёт мелодия.
BOT_KEEP = {"а ты это знал"}


def _old_word(m):
    """Прежняя разметка: слова из одного слога — без ударения."""
    w = m.group(0)
    if "-" in w and "+" in w:
        return w
    return "-".join(x.replace("+", "") if sum(c in VOW for c in x) <= 1 else _bot_part(x) for x in w.split("-"))


def _bot_sent(m):
    s = m.group(0)
    ms = list(WORD.finditer(s))
    if " ".join(w.group(0).replace("+", "").lower() for w in ms) in BOT_KEEP:
        return WORD.sub(_old_word, s)
    cut = len(s) + 1
    if ms and is_yesno(s) and sum(c in VOW for c in ms[-1].group(0)) <= 1:
        k = len(ms) - 1                      # «…во сне?», «…в день?»: взлёт идёт по коротким словам в конце — их не трогаем
        while k >= 1 and len(ms) - k < 3 and sum(c in VOW for c in ms[k].group(0)) <= 1:
            k -= 1
        cut = ms[k].start()
    return _assim(WORD.sub(lambda w: _old_word(w) if w.start() >= cut else _bot_word(w), s))


def bot_marks(marked):
    return _SENT.sub(_bot_sent, marked)


def is_yesno(s0):
    """Вопрос без вопросительного слова: «Верблюд хранит воду в горбу?», «А ты это знал?»."""
    s0 = s0.strip()
    if not s0.endswith("?"):
        return False
    words = [w.replace("+", "").lower() for w in WORD.findall(s0)]
    lead = words[:]
    while lead and lead[0] in ("а", "и", "но", "ну", "так", "вот", "ой"):
        lead = lead[1:]
    return bool(lead) and lead[0] not in _QW and "ли" not in words


def q_win(s0):
    """Длина взлёта, с: по слогам последнего слова (знал — 0,32, горбу — 0,40, слепые — 0,48)."""
    ms = WORD.findall(s0)
    n = sum(c in VOW for c in ms[-1]) if ms else 1
    return min(0.48, 0.22 + 0.10 * max(1, n))


def q_ssml(s0, rate="medium", pitch="medium"):
    """SSML для вопроса без вопросительного слова: последнее слово чуть медленнее."""
    ms = list(WORD.finditer(s0))
    body = s0
    if ms:
        mm = ms[-1]
        body = _dash(s0[:mm.start()]) + '<prosody rate="slow">' + mm.group(0) + "</prosody>" + s0[mm.end():]
    if rate != "medium" or pitch != "medium":
        body = f'<prosody rate="{rate}" pitch="{pitch}">{body}</prosody>'
    return "<speak>" + body + "</speak>"


def q_melody(x, sr, win, low=None, high=None, pre=None):
    """Мелодия вопроса на готовом звуке (numpy float32): провал перед последним словом и взлёт до конца."""
    import numpy as np
    low = BOT_Q_LOW if low is None else low
    high = BOT_Q_HIGH if high is None else high
    pre = BOT_Q_PRE if pre is None else pre
    try:
        import parselmouth
        from parselmouth.praat import call
    except Exception as e:
        print("мелодия вопроса пропущена (нет parselmouth):", e, flush=True)
        return x
    snd = parselmouth.Sound(np.asarray(x, dtype="float64"), sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=600)
    f0 = pitch.selected_array["frequency"]
    voiced = [(t, v) for t, v in zip(pitch.xs(), f0) if v > 0]
    if len(voiced) < 5:
        return x
    base = float(np.median([v for _, v in voiced]))
    te = voiced[-1][0]
    a = te - win

    def sm(u):
        u = min(1.0, max(0.0, u))
        return u * u * (3 - 2 * u)

    manip = call(snd, "To Manipulation", 0.01, 75, 600)
    tier = call(manip, "Extract pitch tier")
    new = call("Create PitchTier", "q", snd.xmin, snd.xmax)
    for i in range(1, call(tier, "Get number of points") + 1):
        t = call(tier, "Get time from index", i)
        v = call(tier, "Get value at index", i)
        if t >= a - pre:
            if t < a:
                cur = 12 * np.log2(max(v, 1.0) / base)
                v = base * 2 ** ((cur + (low - cur) * sm((t - (a - pre)) / pre)) / 12)
            else:
                v = base * 2 ** ((low + (high - low) * sm((t - a) / win)) / 12)
        call(new, "Add point", t, v)
    call([manip, new], "Replace pitch tier")
    out = call(manip, "Get resynthesis (overlap-add)")
    return np.asarray(out.values[0], dtype="float32")


def bot_ssml(marked, rate="medium", pitch="medium"):
    """Текст -> SSML: в вопросе без вопросительного слова последнее слово чуть выше (подъём, как в живой речи)."""
    out = []
    for s in _SENT.findall(marked):
        s0 = s.strip()
        if not s0:
            continue
        words = [w.replace("+", "").lower() for w in WORD.findall(s0)]
        lead = words[:]
        while lead and lead[0] in ("а", "и", "но", "ну", "так", "вот", "ой"):
            lead = lead[1:]
        if BOT_Q_PITCH and s0.endswith("?") and lead and lead[0] not in _QW and "ли" not in words:
            ms = list(WORD.finditer(s0))
            # подъём — на последнем слове; если оно односложное («знал», «нет») — и на предыдущем,
            # а если и то односложное («во сне») — ещё на одном (так проверено 08.11)
            k = len(ms) - 1
            if sum(c in VOW for c in ms[k].group(0)) <= 1 and k >= 1:
                k -= 1
                if sum(c in VOW for c in ms[k].group(0)) <= 1 and k >= 1:
                    k -= 1
            a_, b_ = ms[k].start(), ms[-1].end()
            head = s0[:a_].rstrip()
            if BOT_Q_BASE and head:
                head = f'<prosody pitch="{BOT_Q_BASE}">' + head + "</prosody>"
            s0 = (head + " " if head else "") + f'<prosody pitch="{BOT_Q_PITCH}">' + s0[a_:b_] + "</prosody>" + s0[b_:]
        out.append(s0)
    body = _dash(" ".join(out))
    if rate != "medium" or pitch != "medium":
        body = f'<prosody rate="{rate}" pitch="{pitch}">{body}</prosody>'
    return "<speak>" + body + "</speak>"


def synth_bot(text, speaker, rate, pitch):
    import numpy as np

    def tts(ssml):
        a = model.apply_tts(ssml_text=ssml, speaker=speaker, sample_rate=SR_SYN)
        return a.numpy() if hasattr(a, "numpy") else np.asarray(a)

    pieces = []
    for c in chunks(text):
        c = c.replace("&", " и ").replace("<", " ").replace(">", " ")
        sents = [x.strip() for x in _SENT.findall(c) if x.strip()]
        if not (BOT_Q_MELODY and any(is_yesno(x) for x in sents)):
            pieces.append(tts(bot_ssml(c, rate, pitch)))
            pieces.append(np.zeros(int(SR_SYN * .22), dtype="float32"))
            continue
        # есть вопрос без вопросительного слова: он озвучивается отдельно и получает мелодию вопроса
        buf = []
        for x in sents + [None]:
            if x is not None and not is_yesno(x):
                buf.append(x)
                continue
            if buf:
                pieces.append(tts(bot_ssml(" ".join(buf), rate, pitch)))
                pieces.append(np.zeros(int(SR_SYN * .28), dtype="float32"))
                buf = []
            if x is not None:
                pieces.append(q_melody(tts(q_ssml(x, rate, pitch)), SR_SYN, q_win(x)))
                pieces.append(np.zeros(int(SR_SYN * .28), dtype="float32"))
        pieces[-1] = np.zeros(int(SR_SYN * .22), dtype="float32")
    x = np.concatenate(pieces[:-1]) if pieces else np.zeros(SR_SYN // 4, dtype="float32")
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR_SYN)
        w.writeframes((x * 32767).clip(-32768, 32767).astype("int16").tobytes())
    return b.getvalue()


def marked_for(text, style=""):
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:MAX_TEXT]
    m = mark(text)
    return bot_marks(m) if style == "bot" else m


'''

REPL = [
    # свои голоса «ничьи» (12.11.2026): ru_nash1/2/3 — смесь мужских дикторов той же модели (nash_voices.py + voices.json рядом)
    ('RATES = {"x-slow", "slow", "medium", "fast", "x-fast"}',
     'SPEAKERS |= {"ru_nash1", "ru_nash2", "ru_nash3"}\nRATES = {"x-slow", "slow", "medium", "fast", "x-fast"}'),
    ('        m.to("cpu")\n',
     '        m.to("cpu")\n'
     '        try:\n'
     '            import nash_voices\n'
     '            nash_voices.apply(m, os.path.join(ROOT, "voices.json"))\n'
     '        except Exception as e:\n'
     '            print("свои голоса не подключились:", e, flush=True)\n'),
    ('def make(text, speaker="ru_albina", soft=True, rate="medium", pitch="medium"):',
     'def make(text, speaker="ru_albina", soft=True, rate="medium", pitch="medium", style=""):'),
    ('    key = hashlib.sha1(f"v1|{speaker}|{soft}|{rate}|{pitch}|{text}".encode()).hexdigest()',
     '    style = "bot" if style == "bot" else ""\n'
     '    key = hashlib.sha1((f"v1|{speaker}|{soft}|{rate}|{pitch}|{text}" + ("|bot4" if style else "")).encode()).hexdigest()'),
    ('        raw = synth(mark(text), speaker, rate, pitch)',
     '        raw = synth_bot(bot_marks(mark(text)), speaker, rate, pitch) if style == "bot" else synth(mark(text), speaker, rate, pitch)'),
    ('q.get("rate", "medium"), q.get("pitch", "medium"))',
     'q.get("rate", "medium"), q.get("pitch", "medium"), str(q.get("style", "")))'),
    ('        if u.path == "/tts":\n            return self.tts({k: v[0] for k, v in parse_qs(u.query).items()})',
     '        if u.path == "/tts":\n            return self.tts({k: v[0] for k, v in parse_qs(u.query).items()})\n'
     '        if u.path == "/mark":\n            return self.markq({k: v[0] for k, v in parse_qs(u.query).items()})'),
    ('        if urlparse(self.path).path != "/tts":\n            return self.err(404, "нет такого адреса")',
     '        if urlparse(self.path).path not in ("/tts", "/mark"):\n            return self.err(404, "нет такого адреса")'),
    ('        self.tts(q if isinstance(q, dict) else {})',
     '        q = q if isinstance(q, dict) else {}\n'
     '        return self.markq(q) if urlparse(self.path).path == "/mark" else self.tts(q)'),
    ('    def do_GET(self):',
     '    def markq(self, q):\n'
     '        if not state["ready"]:\n'
     '            return self.err(503, "голос ещё загружается")\n'
     '        try:\n'
     '            with lock:\n'
     '                m = marked_for(q.get("text", ""), str(q.get("style", "")))\n'
     '            self.send(200, json.dumps({"ok": True, "marked": m}, ensure_ascii=False).encode(), "application/json; charset=utf-8")\n'
     '        except Exception as e:\n'
     '            self.err(500, str(e)[:200])\n\n'
     '    def do_GET(self):'),
]


def main(path):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if MARK in s:
        print("   служба голоса: режим для бота уже есть")
        return 0
    for a, _ in REPL:
        if s.count(a) != 1:
            print("   ! служба голоса: server.py не той версии, режим для бота не добавлен (не нашёл: %s)" % a.strip()[:50])
            return 2
    for a, b in REPL:
        s = s.replace(a, b)
    anchor = "class H(BaseHTTPRequestHandler):"
    if s.count(anchor) != 1:
        print("   ! служба голоса: не нашёл class H")
        return 2
    s = s.replace(anchor, BLOCK + anchor)
    p.write_text(s, encoding="utf-8")
    print("   служба голоса: добавлен режим для бота (Мультики не затронуты)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
