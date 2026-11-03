"""Голос «Альбина» (Silero v5 CIS, лицензия MIT) для бота «Почему так?».

Подключение в make_video.py (делает deploy_albina.sh):
    speak = albina.wrap(speak)        — перед def build(
    build = albina.wrap_build(build)  — в конце файла
В config.json: "voices": ["albina"]  (можно "albina@slow", "albina:ru_zinaida", "albina@dry" — без мягкой обработки).

Откуда берётся голос (по порядку):
  1) служба multik-tts на этом же сервере (порт 8095), если она запущена;
  2) свой процесс-озвучщик /opt/multik-tts/venv + albina_worker.py (модель грузится один раз на ролик,
     после ролика память освобождается);
  3) если не вышло — весь ролик прежним голосом (Microsoft «Дмитрий»), ролик всё равно выходит.

Текст перед озвучкой: цифры -> слова (с падежами для «в 1969 году», «10%», «км/ч»), словарь своих
ударений albina_fix.json, остальные ударения и «ё» ставит ruaccent.

Проверка руками:  python3 albina.py "Почему лёд не тонет?" /tmp/test.mp3
"""
import atexit
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TTS_DIR = Path(os.environ.get("ALBINA_DIR", "/opt/multik-tts"))
SERVICE = os.environ.get("ALBINA_URL", "http://127.0.0.1:8095")
FALLBACK = "ru-RU-DmitryNeural"
FIX_FILE = HERE / "albina_fix.json"
RATES = ("x-slow", "slow", "medium", "fast", "x-fast")
PITCHES = ("x-low", "low", "medium", "high", "x-high")
VOW = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"


class AlbinaFailed(RuntimeError):
    pass


_st = {"off": False, "proc": None, "mode": None, "fix": None, "log": print, "n": 0,
       "said": False, "last": "", "rss": None}


def _log(msg):
    try:
        _st["log"](msg)
    except Exception:
        print(msg, flush=True)


# ---------------- голос из config.json ----------------

def is_albina(voice):
    return str(voice or "").lower().startswith(("albina", "silero"))


def parse(voice):
    """albina | albina@slow,low | albina:ru_zinaida@dry  ->  (speaker, soft, rate, pitch)"""
    name, _, opts = str(voice).partition("@")
    spk = name.split(":", 1)[1].strip() if ":" in name else "ru_albina"
    if not spk.startswith("ru_"):
        spk = "ru_" + spk
    o = [x.strip().lower() for x in opts.split(",") if x.strip()]
    rate = next((x for x in o if x in RATES), "medium")
    pitch = next((x for x in o if x in PITCHES), "medium")
    return spk, ("dry" not in o), rate, pitch


# ---------------- цифры словами ----------------

_U_M = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_U_F = ["", "одна", "две"] + _U_M[3:]
_TEEN = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
         "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят",
         "восемьдесят", "девяносто"]
_HUN = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот",
        "восемьсот", "девятьсот"]
# основы порядковых (для «в 1969 году», «с 1990 года», «в 19 веке»)
_O_U = ["", "перв", "втор", "трет", "четвёрт", "пят", "шест", "седьм", "восьм", "девят"]
_O_TEEN = ["десят", "одиннадцат", "двенадцат", "тринадцат", "четырнадцат", "пятнадцат",
           "шестнадцат", "семнадцат", "восемнадцат", "девятнадцат"]
_O_TENS = ["", "", "двадцат", "тридцат", "сороков", "пятидесят", "шестидесят", "семидесят",
           "восьмидесят", "девяност"]
_O_HUN = ["", "сот", "двухсот", "трёхсот", "четырёхсот", "пятисот", "шестисот", "семисот",
          "восьмисот", "девятисот"]
_O_THOU = {1: "тысячн", 2: "двухтысячн", 3: "трёхтысячн", 4: "четырёхтысячн", 5: "пятитысячн"}

# 1 и 2 с существительными женского рода, 1 — среднего
_FEM = ("минут", "секунд", "недел", "тысяч", "частиц", "част", "клетк", "звезд", "звёзд", "планет", "ног",
        "лап", "рук", "тонн", "капл", "молекул", "голов", "птиц", "рыб", "мыш", "пчёл", "пчел", "ягод",
        "сторон", "ветк", "единиц", "калори", "страниц", "сотн", "челюст", "камер", "ступен", "волн",
        "точк", "букв", "цифр", "жизн", "ночь", "ночи", "зим", "весн", "осен", "доли", "треть", "четверт",
        "минут", "кошк", "собак", "черепах", "акул", "змеи", "змея", "бактери", "планк")
_NEU = {"сердце", "крыло", "яйцо", "щупальце", "место", "слово", "солнце", "озеро", "море", "окно",
        "дерево", "колесо", "животное", "насекомое", "растение", "существо", "тело", "лёгкое", "ухо", "око"}


def _plural(n, one, few, many):
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    n %= 10
    return one if n == 1 else few if 2 <= n <= 4 else many


def _one(n):
    return n % 10 == 1 and n % 100 != 11


_G_U = ["", "одного", "двух", "трёх", "четырёх", "пяти", "шести", "семи", "восьми", "девяти"]
_G_TEEN = [w[:-1] + "и" for w in _TEEN]
_G_TENS = ["", "", "двадцати", "тридцати", "сорока", "пятидесяти", "шестидесяти", "семидесяти",
           "восьмидесяти", "девяноста"]
_G_HUN = ["", "ста", "двухсот", "трёхсот", "четырёхсот", "пятисот", "шестисот", "семисот",
          "восьмисот", "девятисот"]


def _tri(n, gender="m", case="nom"):
    g = case == "gen"
    w = []
    if n >= 100:
        w.append((_G_HUN if g else _HUN)[n // 100]); n %= 100
    if 10 <= n <= 19:
        w.append((_G_TEEN if g else _TEEN)[n - 10]); return w
    if n >= 20:
        w.append((_G_TENS if g else _TENS)[n // 10]); n %= 10
    if n:
        if g:
            w.append("одной" if (n == 1 and gender == "f") else _G_U[n])
        elif n == 1 and gender == "n":
            w.append("одно")
        else:
            w.append((_U_F if gender == "f" else _U_M)[n])
    return w


def cardinal(n, gender="m", case="nom"):
    """Число словами: case = nom (сколько? — «двадцать») или gen (около скольких? — «двадцати»)."""
    if n == 0:
        return "ноля" if case == "gen" else "ноль"
    w = []
    if n < 0:
        w.append("минус"); n = -n
    for val, forms, g in ((10 ** 9, ("миллиард", "миллиарда", "миллиардов"), "m"),
                          (10 ** 6, ("миллион", "миллиона", "миллионов"), "m"),
                          (1000, ("тысяча", "тысячи", "тысяч"), "f")):
        q, n = divmod(n, val)
        if not q:
            continue
        if case == "gen":
            noun = forms[1] if _one(q) else forms[2]
        else:
            noun = _plural(q, *forms)
        if q == 1 and val == 1000:            # «тысяча», а не «одна тысяча»
            w.append(noun)
        else:
            w += _tri(q, g, case) + [noun]
    if n:
        w += _tri(n, gender, case)
    return " ".join(w)


def _noun(n, forms, case="nom"):
    """Форма слова после числа: 1 процент, 2 процента, 5 процентов; около 1 процента, около 2 процентов."""
    if case == "gen":
        return forms[1] if _one(n) else forms[2]
    return _plural(n, *forms)


def ordinal(n, case="prep"):
    """Порядковое мужского рода: case = prep (в каком? — «девятом») или gen (какого? — «девятого»)."""
    end = {"prep": "ом", "gen": "ого"}[case]
    if n <= 0:
        return cardinal(n)
    r100 = n % 100
    if n % 10 and not 10 <= r100 <= 19:
        head, stem = n - n % 10, _O_U[n % 10]
    elif 10 <= r100 <= 19:
        head, stem = n - r100, _O_TEEN[r100 - 10]
    elif r100:
        head, stem = n - r100, _O_TENS[r100 // 10]
    elif n % 1000:
        head, stem = n - n % 1000, _O_HUN[(n % 1000) // 100]
    elif n % 10 ** 6 and (n // 1000) % 1000 in _O_THOU:
        head, stem = n - n % 10 ** 6, _O_THOU[(n // 1000) % 1000]
    else:
        return cardinal(n)
    if stem == "трет":
        word = "третьем" if case == "prep" else "третьего"
    else:
        word = stem + end
    return (cardinal(head) + " " + word).strip() if head else word


def _gender_of(nxt):
    w = (nxt or "").lower()
    if w in _NEU:
        return "n"
    if w.startswith(_FEM) and not w.startswith(("ноготь", "ногт", "головаст", "рукав", "рыбак", "частник")):
        return "f"
    return "m"


def _num(s):
    return int(re.sub(r"[\s  ]", "", s))


def _frac(a, b, case="nom", gender="m"):
    """1,5 -> полтора (около полутора); 2,5 -> две целых пять десятых. Возвращает (слова, n для формы слова)."""
    ia, ib = _num(a), _num(b)
    if ia == 1 and b == "5":
        return ("полутора" if case == "gen" else "полторы" if gender == "f" else "полтора"), 2
    den = {1: ("десятая", "десятых"), 2: ("сотая", "сотых"), 3: ("тысячная", "тысячных")}.get(len(b))
    if not den:
        return cardinal(ia) + " и " + cardinal(ib), ib
    whole = cardinal(ia, "f") + " " + ("целая" if _one(ia) else "целых")
    part = cardinal(ib, "f") + " " + (den[0] if _one(ib) else den[1])
    return whole + " " + part, 2


_UNITS = [
    (r"км/ч|км/час", ("километр", "километра", "километров"), " в час"),
    (r"м/с", ("метр", "метра", "метров"), " в секунду"),
    (r"км", ("километр", "километра", "километров"), ""),
    (r"кг", ("килограмм", "килограмма", "килограммов"), ""),
    (r"см", ("сантиметр", "сантиметра", "сантиметров"), ""),
    (r"мм", ("миллиметр", "миллиметра", "миллиметров"), ""),
    (r"°\s?[CС]", ("градус", "градуса", "градусов"), " Цельсия"),
    (r"°", ("градус", "градуса", "градусов"), ""),
    (r"%", ("процент", "процента", "процентов"), ""),
    (r"млн", ("миллион", "миллиона", "миллионов"), ""),
    (r"млрд", ("миллиард", "миллиарда", "миллиардов"), ""),
    (r"тыс\.?", ("тысяча", "тысячи", "тысяч"), ""),
]
_N = r"\d{1,3}(?:[   ]\d{3})+(?!\d)|\d+"
_GEN = "\x01"   # метка: число стоит после «около», «до», «больше»… (родительный падеж)
_GEN_WORDS = r"около|до|от|больше|меньше|более|менее|свыше|из|без|со?|после|кроме|среди|порядка|примерно до|не больше|не меньше"


def numbers(text):
    t = text
    # годы и века с падежом
    t = re.sub(r"\b([вВ]о?)\s+(\d{3,4})(?:-?м)?\s+(году)\b",
               lambda m: f"{m.group(1)} {ordinal(int(m.group(2)), 'prep')} {m.group(3)}", t)
    t = re.sub(r"\b([вВ])\s+(\d{1,2})(?:-?м)?\s+(веке)\b",
               lambda m: f"{m.group(1)} {ordinal(int(m.group(2)), 'prep')} {m.group(3)}", t)
    t = re.sub(r"\b(\d{3,4})(?:-?го)?\s+(года)\b",
               lambda m: f"{ordinal(int(m.group(1)), 'gen')} {m.group(2)}", t)
    if not re.search(r"\d", t):
        return t
    t = re.sub(r"(?i)\b(" + _GEN_WORDS + r")(\s+)(?=\d)", lambda m: m.group(1) + m.group(2) + _GEN, t)
    # единицы и проценты: 100 км/ч, 1,5 кг, 40 °C, 10%
    for pat, forms, tail in _UNITS:
        def unit(m, forms=forms, tail=tail):
            case = "gen" if m.group(1) else "nom"
            g = "f" if forms[0] == "тысяча" else "m"
            if m.group(3):
                w, k = _frac(m.group(2), m.group(3), case, g)
                return w + " " + (forms[2] if w == "полутора" else forms[1]) + tail
            n = _num(m.group(2))
            return cardinal(n, g, case) + " " + _noun(n, forms, case) + tail
        t = re.sub("(" + _GEN + r")?(" + _N + r")(?:[.,](\d+))?\s?(?:" + pat + r")(?![А-Яа-яЁё])", unit, t)
    # дроби
    t = re.sub("(" + _GEN + r")?\b(\d+)[.,](\d+)\b",
               lambda m: _frac(m.group(2), m.group(3), "gen" if m.group(1) else "nom")[0], t)
    # остальные числа (род — по следующему слову: две минуты, одно сердце)
    t = re.sub("(" + _GEN + r")?(" + _N + r")(\s+)([А-Яа-яЁё]+)?",
               lambda m: cardinal(_num(m.group(2)), _gender_of(m.group(4)), "gen" if m.group(1) else "nom")
               + m.group(3) + (m.group(4) or ""), t)
    t = re.sub("(" + _GEN + r")?(\d+)", lambda m: cardinal(int(m.group(2)), "m", "gen" if m.group(1) else "nom"), t)
    return t.replace(_GEN, "")


# ---------------- свои ударения ----------------

_WORD = re.compile(r"[А-Яа-яЁё+]+(?:-[А-Яа-яЁё+]+)*")


def _fixes():
    if _st["fix"] is None:
        try:
            d = json.loads(FIX_FILE.read_text(encoding="utf-8"))
            _st["fix"] = {k.lower().replace("+", ""): v for k, v in d.items() if not k.startswith("_")}
        except Exception:
            _st["fix"] = {}
    return _st["fix"]


def apply_fix(text):
    fx = _fixes()
    if not fx:
        return text

    def one(m):
        w = m.group(0)
        if "+" in w:
            return w
        v = fx.get(w.lower())
        if not v:
            return w
        if w[:1].isupper():
            v = v[:1].upper() + v[1:] if v[:1] != "+" else "+" + v[1:2].upper() + v[2:]
        return v
    return _WORD.sub(one, text)


def prep(text):
    t = str(text or "")
    t = re.sub(r"([" + VOW + r"])́", r"+\1", t)        # знак ударения -> «+»
    t = t.replace("«", "").replace("»", "").replace("„", "").replace("“", "").replace("”", "")
    t = t.replace("…", "...").replace(" ", " ")
    t = numbers(t)
    t = apply_fix(t)
    return re.sub(r"\s+", " ", t).strip()


def plain(text):
    """Как текст должен прозвучать (без «+») — эталон для проверки."""
    return prep(text).replace("+", "")


# ---------------- озвучка ----------------

def _service_ready():
    try:
        with urllib.request.urlopen(SERVICE + "/health", timeout=2) as r:
            return json.load(r).get("ready") is True
    except Exception:
        return False


def _readline(p, timeout):
    box = []
    th = threading.Thread(target=lambda: box.append(p.stdout.readline()), daemon=True)
    th.start()
    th.join(timeout)
    if not box or not box[0]:
        raise AlbinaFailed("озвучщик не ответил" if not box else "озвучщик закрылся")
    return json.loads(box[0])


def _worker():
    p = _st["proc"]
    if p and p.poll() is None:
        return p
    py, w = TTS_DIR / "venv" / "bin" / "python", TTS_DIR / "albina_worker.py"
    if not py.exists() or not w.exists():
        raise AlbinaFailed(f"озвучщик не установлен ({TTS_DIR})")
    env = dict(os.environ, HF_HOME=str(TTS_DIR / "hf"), OMP_NUM_THREADS="2", PYTHONUNBUFFERED="1",
               TOKENIZERS_PARALLELISM="false")
    errlog = open(TTS_DIR / "worker.log", "a", encoding="utf-8")
    cmd = [str(py), str(w)]
    if os.name == "posix" and Path("/usr/bin/nice").exists():
        cmd = ["/usr/bin/nice", "-n", "10"] + cmd  # не мешать VPN
    t0 = time.time()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errlog,
                         text=True, encoding="utf-8", cwd=str(TTS_DIR), env=env)
    _st["proc"] = p
    hello = _readline(p, 900)
    if not hello.get("ready"):
        close()
        raise AlbinaFailed("голос не загрузился: " + str(hello.get("error")))
    _st["rss"] = hello.get("rss_mb")
    _log(f"Альбина: голос загружен за {time.time() - t0:.0f} с (память {hello.get('rss_mb')} МБ)")
    return p


def _synth(text, spk, soft, rate, pitch, wav):
    q = {"text": text, "speaker": spk, "soft": soft, "rate": rate, "pitch": pitch}
    if _st["mode"] in (None, "service") and _service_ready():
        req = urllib.request.Request(SERVICE + "/tts", data=json.dumps(q, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        if len(data) < 4000:
            raise AlbinaFailed("служба вернула пустой звук")
        wav.write_bytes(data)
        _st["mode"] = "service"
        return ""
    _st["mode"] = "worker"
    p = _worker()
    q["out"] = str(wav)
    p.stdin.write(json.dumps(q, ensure_ascii=False) + "\n")
    p.stdin.flush()
    r = _readline(p, 300)
    if not r.get("ok"):
        raise AlbinaFailed(r.get("error") or "ошибка озвучки")
    return r.get("marked") or ""


def _to_audio(wav, path):
    """wav -> файл, который ждёт бот (mp3), без лишней тишины в начале и в конце."""
    af = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse,"
          "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.10,areverse")
    codec = ["-c:a", "libmp3lame", "-q:a", "2"] if path.suffix.lower() == ".mp3" else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", af, "-ar", "44100", "-ac", "1",
                        *codec, str(path)], capture_output=True, text=True)
    if r.returncode or not path.exists() or path.stat().st_size < 1500:
        raise AlbinaFailed("ffmpeg: " + r.stderr[-300:])


def say(text, voice, path):
    path = Path(path)
    spk, soft, rate, pitch = parse(voice)
    t = prep(text)
    if not re.search(r"[А-Яа-яЁё]", t):
        raise AlbinaFailed("в фразе нет русских слов")
    wav = path.with_name(path.stem + "_albina.wav")
    err = None
    for k in range(2):
        try:
            t0 = time.time()
            marked = _synth(t, spk, soft, rate, pitch, wav)
            _to_audio(wav, path)
            _st["last"] = marked or t
            _st["n"] += 1
            if not _st["said"]:
                _st["said"] = True
                _log("Озвучка: Альбина (" + ("служба multik-tts" if _st["mode"] == "service" else "свой процесс")
                     + f"), первая фраза за {time.time() - t0:.0f} с")
            if marked:
                _log("  ударения: " + marked)
            try:
                wav.unlink()
            except OSError:
                pass
            return
        except Exception as e:
            err = e
            close()                      # перезапустить озвучщик и попробовать ещё раз
            _st["mode"] = None
    raise AlbinaFailed(str(err))


def close():
    p, _st["proc"] = _st["proc"], None
    if not p:
        return
    try:
        p.stdin.write('{"cmd": "quit"}\n'); p.stdin.flush(); p.stdin.close()
        p.wait(10)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


atexit.register(close)


# ---------------- подключение к боту ----------------

def wrap(orig):
    if getattr(orig, "_albina", False):
        return orig

    def speak(text, voice, rate="+0%", path=None, *a, **k):
        if not is_albina(voice):
            return orig(text, voice, rate, path, *a, **k)
        if not _st["off"]:
            try:
                return say(text, voice, path)
            except AlbinaFailed as e:
                if _st["n"]:             # часть ролика уже Альбиной — пусть build соберёт всё заново
                    raise
                _log(f"Альбина недоступна ({e}) — ролик прежним голосом")
                _st["off"] = True
        return orig(text, FALLBACK, "+0%", path, *a, **k)
    speak._albina = True
    speak._orig = orig
    return speak


def wrap_build(orig):
    if getattr(orig, "_albina", False):
        return orig

    def build(*a, **k):
        _st["log"] = k.get("log") or print
        _st["n"] = 0
        try:
            try:
                return orig(*a, **k)
            except AlbinaFailed as e:
                _log(f"Альбина сбилась посреди ролика ({e}) — собираю весь ролик прежним голосом")
                _st["off"] = True
                _st["n"] = 0
                return orig(*a, **k)
        finally:
            close()                      # освободить память сразу после ролика
    build._albina = True
    build._orig = orig
    return build


def selftest(text="Почему так? Это проверка голоса Альбины для роликов.", out="/tmp/albina_test.mp3"):
    t0 = time.time()
    try:
        say(text, "albina", out)
    except Exception as e:
        print("ОШИБКА: Альбина не озвучила:", e)
        return 1
    dur = "?"
    try:
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                              "default=nw=1:nk=1", out], capture_output=True, text=True).stdout.strip()[:4]
    except Exception:
        pass
    print(f"Альбина работает ({'служба multik-tts' if _st['mode'] == 'service' else 'свой процесс'}): "
          f"{time.time() - t0:.0f} с, звук {dur} с, память озвучщика {_st['rss'] or '—'} МБ")
    print("Ударения:", _st["last"])
    close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        v = sys.argv[3] if len(sys.argv) > 3 else "albina"
        say(sys.argv[1], v, sys.argv[2])
        print(_st["last"])
        close()
    elif len(sys.argv) == 2 and sys.argv[1] == "--prep":
        for line in sys.stdin:
            print(prep(line))
    else:
        sys.exit(selftest())
