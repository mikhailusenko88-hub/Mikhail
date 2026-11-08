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
BOT_Q_PITCH = "x-high"  # подъём в конце вопроса без вопросительного слова ("" — выключить)
BOT_Q_BASE = "low"      # начало такого вопроса ниже — так подъём слышен (пробы 08.11: вопрос слышен в 6 из 7, было 0 из 3)


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


def _bot_part(w):
    if sum(c in VOW for c in w) <= 1:
        return w.replace("+", "")          # односложные — без ударения
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
    return "-".join(_bot_part(x) for x in w.split("-"))


def bot_marks(marked):
    return WORD.sub(_bot_word, marked)


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
    body = " ".join(out)
    if rate != "medium" or pitch != "medium":
        body = f'<prosody rate="{rate}" pitch="{pitch}">{body}</prosody>'
    return "<speak>" + body + "</speak>"


def synth_bot(text, speaker, rate, pitch):
    import numpy as np
    pieces = []
    for c in chunks(text):
        c = c.replace("&", " и ").replace("<", " ").replace(">", " ")
        a = model.apply_tts(ssml_text=bot_ssml(c, rate, pitch), speaker=speaker, sample_rate=SR_SYN)
        pieces.append(a.numpy() if hasattr(a, "numpy") else np.asarray(a))
        pieces.append(np.zeros(int(SR_SYN * .22), dtype="float32"))
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
    ('def make(text, speaker="ru_albina", soft=True, rate="medium", pitch="medium"):',
     'def make(text, speaker="ru_albina", soft=True, rate="medium", pitch="medium", style=""):'),
    ('    key = hashlib.sha1(f"v1|{speaker}|{soft}|{rate}|{pitch}|{text}".encode()).hexdigest()',
     '    style = "bot" if style == "bot" else ""\n'
     '    key = hashlib.sha1((f"v1|{speaker}|{soft}|{rate}|{pitch}|{text}" + ("|bot3" if style else "")).encode()).hexdigest()'),
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
