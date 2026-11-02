#!/usr/bin/env python3
# Голос рассказчика для «Мультиков» (приложение «Замер 3D»): нейроголос Silero v5 CIS (лицензия MIT),
# ударения — ruaccent (там, где их не поставили в сценарии), «мягкий тон» — та же обработка ffmpeg,
# что выбрали на слух 2 ноября 2026 («Альбина, мягкий тон»).
#   GET  /health                       — {"ok": true, "ready": true/false}
#   GET  /tts?text=Привет&speaker=…    — wav (послушать прямо в браузере телефона)
#   POST /tts {"text", "speaker", "soft", "rate", "pitch"} — wav
import hashlib, io, json, os, re, subprocess, threading, time, wave
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "cache")
MODEL = os.path.join(ROOT, "v5_cis_base.pt")
PORT = int(os.environ.get("PORT", "8095"))
SR_SYN, SR_OUT = 48000, 32000
MAX_TEXT = 1500
CACHE_MB = 400
SPEAKERS = {"ru_albina", "ru_zinaida", "ru_ekaterina", "ru_alexandr", "ru_aigul", "ru_eduard"}
RATES = {"x-slow", "slow", "medium", "fast", "x-fast"}
PITCHES = {"x-low", "low", "medium", "high", "x-high"}
VOW = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
SOFT = ("highpass=f=70,bass=g=2.5:f=160:w=0.7,equalizer=f=3200:t=q:w=1.0:g=-2.5,deesser=i=0.35,"
        "acompressor=threshold=-22dB:ratio=2.2:attack=12:release=220:makeup=1.5,"
        "aecho=0.85:0.6:28|47:0.08|0.05,loudnorm=I=-16:TP=-1.5:LRA=9")

os.makedirs(CACHE, exist_ok=True)
state = {"ready": False, "error": None}
lock = threading.Lock()
model = acc = None


def load():
    global model, acc
    try:
        import torch
        torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
        m = torch.package.PackageImporter(MODEL).load_pickle("tts_models", "model")
        m.to("cpu")
        from ruaccent import RUAccent
        a = RUAccent()
        for size in ["turbo3.1", "turbo3", "turbo2", "turbo", "tiny2", "tiny"]:
            try:
                a.load(omograph_model_size=size, use_dictionary=True)
                break
            except Exception:
                continue
        model, acc = m, a
        with lock:
            synth("Готово.", "ru_albina", "medium", "medium")  # прогрев
        state["ready"] = True
        print("голос готов", flush=True)
    except Exception as e:
        state["error"] = str(e)
        print("ошибка загрузки:", e, flush=True)


WORD = re.compile(r"[А-Яа-яЁё+]+(?:-[А-Яа-яЁё+]+)*")


def mark(text):
    """Ударения: свои «+» из сценария оставляем, остальные ставит ruaccent (и «ё» тоже)."""
    text = re.sub(r"([" + VOW + r"])́", r"+\1", text)
    plain = text.replace("+", "")
    try:
        res = acc.process_all(plain)
    except Exception:
        return text
    mine, theirs = WORD.findall(text), WORD.findall(res)
    if len(mine) != len(theirs):
        return res if "+" not in text else text
    it = iter(zip(mine, theirs))
    def pick(_m):
        a, b = next(it)
        return a if "+" in a else b
    return WORD.sub(pick, text)


def chunks(text, n=700):
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if cur and len(cur) + len(s) + 1 > n:
            parts.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        parts.append(cur)
    out = []
    for p in parts:  # совсем длинное предложение — по запятым
        while len(p) > n:
            k = p.rfind(",", 0, n)
            k = k if k > 50 else n
            out.append(p[:k + 1]); p = p[k + 1:].strip()
        if p:
            out.append(p)
    return out


def synth(text, speaker, rate, pitch):
    import numpy as np
    pieces = []
    for c in chunks(text):
        c = c.replace("&", " и ").replace("<", " ").replace(">", " ")
        if rate != "medium" or pitch != "medium":
            a = model.apply_tts(ssml_text=f'<speak><prosody rate="{rate}" pitch="{pitch}">{c}</prosody></speak>', speaker=speaker, sample_rate=SR_SYN)
        else:
            a = model.apply_tts(text=c, speaker=speaker, sample_rate=SR_SYN)
        pieces.append(a.numpy() if hasattr(a, "numpy") else np.asarray(a))
        pieces.append(np.zeros(int(SR_SYN * .22), dtype="float32"))
    x = np.concatenate(pieces[:-1]) if pieces else np.zeros(SR_SYN // 4, dtype="float32")
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR_SYN)
        w.writeframes((x * 32767).clip(-32768, 32767).astype("int16").tobytes())
    return b.getvalue()


def make(text, speaker="ru_albina", soft=True, rate="medium", pitch="medium"):
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:MAX_TEXT]
    if not re.search(r"[А-Яа-яЁё]", text):
        raise ValueError("нет русского текста")
    speaker = speaker if speaker in SPEAKERS else "ru_albina"
    rate = rate if rate in RATES else "medium"
    pitch = pitch if pitch in PITCHES else "medium"
    key = hashlib.sha1(f"v1|{speaker}|{soft}|{rate}|{pitch}|{text}".encode()).hexdigest()
    f = os.path.join(CACHE, key + ".wav")
    if os.path.exists(f):
        os.utime(f, None)
        return open(f, "rb").read()
    with lock:
        raw = synth(mark(text), speaker, rate, pitch)
    af = (SOFT + "," if soft else "") + "aresample=%d" % SR_OUT
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "wav", "-i", "pipe:0", "-af", af, "-ac", "1", "-ar", str(SR_OUT), "-f", "wav", "pipe:1"],
                       input=raw, stdout=subprocess.PIPE, check=True)
    out = p.stdout
    tmp = f + ".tmp"
    open(tmp, "wb").write(out); os.replace(tmp, f)
    prune()
    return out


def prune():
    fs = [os.path.join(CACHE, x) for x in os.listdir(CACHE) if x.endswith(".wav")]
    tot = sum(os.path.getsize(x) for x in fs)
    if tot < CACHE_MB * 1e6:
        return
    for x in sorted(fs, key=os.path.getmtime):
        tot -= os.path.getsize(x); os.remove(x)
        if tot < CACHE_MB * .8e6:
            break


class H(BaseHTTPRequestHandler):
    server_version = "multik-tts/1"

    def log_message(self, fmt, *a):
        pass

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def err(self, code, msg):
        self.send(code, json.dumps({"ok": False, "error": msg}, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def tts(self, q):
        if not state["ready"]:
            return self.err(503, "голос ещё загружается" if not state["error"] else state["error"])
        try:
            t0 = time.time()
            wav = make(q.get("text", ""), q.get("speaker", "ru_albina"), str(q.get("soft", "1")).lower() not in ("0", "false", "no"), q.get("rate", "medium"), q.get("pitch", "medium"))
            print("озвучено за %.1f с: %s" % (time.time() - t0, str(q.get("text", ""))[:60]), flush=True)
            self.send(200, wav, "audio/wav")
        except ValueError as e:
            self.err(400, str(e))
        except Exception as e:
            print("ошибка:", e, flush=True)
            self.err(500, "не получилось озвучить")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            return self.send(200, json.dumps({"ok": True, "ready": state["ready"], "error": state["error"]}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
        if u.path == "/tts":
            return self.tts({k: v[0] for k, v in parse_qs(u.query).items()})
        self.err(404, "нет такого адреса")

    def do_POST(self):
        if urlparse(self.path).path != "/tts":
            return self.err(404, "нет такого адреса")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            return self.err(413, "слишком длинный текст")
        try:
            q = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.err(400, "неверный запрос")
        self.tts(q if isinstance(q, dict) else {})


if __name__ == "__main__":
    threading.Thread(target=load, daemon=True).start()
    print("слушаю порт", PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
