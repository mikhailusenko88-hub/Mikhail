# Ядро дубляжа «Кот Барсик»: фраза на нужном языке голосом героя.
# Источник с родным произношением (Kokoro: en/es/pt; Piper: de) → по желанию подъём высоты источника (Praat)
# → Chatterbox VC перекрашивает в голос героя по образцу → высота к образцу героя (Praat), если расходится.
# Проверки: высота/размах/HNR (Praat), разборчивость (Whisper), узнаваемость (ECAPA, сходство с образцами героев).
import asyncio, difflib, inspect, os, re, subprocess, time, traceback, wave

import numpy as np
import soundfile as sf
import torch

_orig_load = torch.load


def _cpu_load(*a, **k):
    k.setdefault("map_location", "cpu")
    return _orig_load(*a, **k)


torch.load = _cpu_load
torch.set_num_threads(max(1, os.cpu_count() or 4))

import parselmouth  # noqa: E402
from parselmouth.praat import call  # noqa: E402

SR = 24000
TMP = os.environ.get("DUB_TMP", "tmp_dub")
os.makedirs(TMP, exist_ok=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def call_kw(fn, **kw):
    sig = inspect.signature(fn)
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(**kw)
    return fn(**{k: v for k, v in kw.items() if k in sig.parameters})


def to_np(w):
    if hasattr(w, "detach"):
        w = w.detach().cpu().numpy()
    a = np.asarray(w, dtype=np.float32)
    return a.reshape(-1) if a.ndim > 1 else a


def load(path, sr=SR):
    a, s = sf.read(path, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if s != sr:
        tmp = os.path.join(TMP, "rs_" + os.path.basename(path).rsplit(".", 1)[0] + f"_{sr}.wav")
        ff("-i", path, "-ac", "1", "-ar", str(sr), tmp)
        a, _ = sf.read(tmp, dtype="float32")
    return a


def save(arr, path, sr=SR):
    sf.write(path, np.asarray(arr, dtype=np.float32), sr)
    return path


def resample(arr, sr_from, sr_to=SR):
    if sr_from == sr_to:
        return arr
    a = os.path.join(TMP, "rsa.wav")
    b = os.path.join(TMP, "rsb.wav")
    sf.write(a, arr, sr_from)
    ff("-i", a, "-ac", "1", "-ar", str(sr_to), b)
    return load(b, sr_to)


def silence(sec, sr=SR):
    return np.zeros(int(sr * sec), dtype=np.float32)


def snd(arr, sr=SR):
    return parselmouth.Sound(np.asarray(arr, dtype=np.float64), sampling_frequency=sr)


def measure(arr, sr=SR):
    s = snd(arr, sr)
    p = s.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=700).selected_array["frequency"]
    v = p[p > 0]
    if len(v) < 5:
        return {"f0": None, "range_st": None, "hnr": None}
    p10, p90 = np.percentile(v, [10, 90])
    h = s.to_harmonicity_cc(time_step=0.01, minimum_pitch=75).values
    h = h[h > -200]
    return {"f0": round(float(np.median(v)), 1), "range_st": round(float(12 * np.log2(p90 / p10)), 1),
            "hnr": round(float(np.mean(h)), 1) if len(h) else None}


def change(arr, f0=0.0, F=1.0, rng=1.0, dur=1.0, sr=SR):
    """Praat «Change gender»: новая средняя высота f0 (0 — не менять), форманты ×F, размах ×rng, длина ×dur."""
    if not f0 and F == 1.0 and rng == 1.0 and dur == 1.0:
        return arr
    out = call(snd(arr, sr), "Change gender", 75, 700, float(F), float(f0 or 0), float(rng), float(dur))
    a = np.asarray(out.values[0], dtype=np.float32)
    pk = float(np.max(np.abs(a))) or 1.0
    return a / pk * 0.9 if pk > 0.99 else a


def match_pitch(arr, f0_ref, thr=1.5):
    m = measure(arr)
    if not m["f0"] or not f0_ref:
        return arr, 0.0
    st = 12 * np.log2(f0_ref / m["f0"])
    if abs(st) <= thr:
        return arr, 0.0
    return change(arr, f0=f0_ref), round(float(st), 1)


def rms(arr):
    a = np.asarray(arr, dtype=np.float64)
    return float(np.sqrt(np.mean(a * a))) if len(a) else 0.0


def trim(arr, db=-45, pad=0.04, sr=SR):
    """Срезать тишину в начале и конце (оставить pad секунд)."""
    a = np.abs(arr)
    thr = (10 ** (db / 20)) * (float(a.max()) or 1.0)
    idx = np.where(a > thr)[0]
    if not len(idx):
        return arr
    i0 = max(0, idx[0] - int(pad * sr))
    i1 = min(len(arr), idx[-1] + int(pad * sr))
    return arr[i0:i1]


def tempo(arr, k, sr=SR):
    """Ускорить в k раз без смены высоты (ffmpeg atempo)."""
    if abs(k - 1.0) < 0.01:
        return arr
    a = os.path.join(TMP, "tp_a.wav")
    b = os.path.join(TMP, "tp_b.wav")
    sf.write(a, arr, sr)
    ff("-i", a, "-af", f"atempo={k:.4f}", "-ar", str(sr), "-ac", "1", b)
    return load(b, sr)


# ---------- источники ----------
_kp, _pv = {}, {}


def kokoro(text, lang, voice, speed=1.0):
    from kokoro import KPipeline
    if lang not in _kp:
        _kp[lang] = KPipeline(lang_code=lang)
    parts = [to_np(a) for _, _, a in _kp[lang](text, voice=voice, speed=speed) if a is not None]
    return np.concatenate(parts) if parts else silence(0.1)


def piper(text, model, speed=1.0):
    """model — путь в rhasspy/piper-voices без расширения, например de/de_DE/thorsten/high/de_DE-thorsten-high."""
    from huggingface_hub import hf_hub_download
    from piper import PiperVoice
    if model not in _pv:
        onnx = hf_hub_download("rhasspy/piper-voices", model + ".onnx")
        hf_hub_download("rhasspy/piper-voices", model + ".onnx.json")
        _pv[model] = PiperVoice.load(onnx)
    v = _pv[model]
    tmp = os.path.join(TMP, "piper.wav")
    with wave.open(tmp, "wb") as w:
        if hasattr(v, "synthesize_wav"):
            try:
                from piper import SynthesisConfig
                v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.0 / speed))
            except Exception:
                v.synthesize_wav(text, w)
        else:
            v.synthesize(text, w, length_scale=1.0 / speed)
    return load(tmp)


def source(text, spec):
    if spec["engine"] == "kokoro":
        return kokoro(text, spec["lang"], spec["voice"], spec.get("speed", 1.0))
    if spec["engine"] == "piper":
        return piper(text, spec["model"], spec.get("speed", 1.0))
    if spec["engine"] == "mtl":
        # Chatterbox Multilingual с образцом родного голоса (например, сделанным Piper) — родное произношение, звук 24 кГц
        return mtl(text, spec["lang"], spec_ref(spec), spec.get("speed", 1.0), spec.get("cfg", 0.5), spec.get("exag", 0.5))
    if spec["engine"] == "silma":
        # SILMA TTS (арабский): отдельное окружение, сервер silma_srv.py; огласовки ставит CATT
        return silma(text, spec)
    if spec["engine"] == "edge":
        import edge_tts
        mp3 = os.path.join(TMP, "edge.mp3")
        asyncio.run(edge_tts.Communicate(text, spec["voice"], rate=spec.get("rate", "+0%")).save(mp3))
        w = os.path.join(TMP, "edge.wav")
        ff("-i", mp3, "-ac", "1", "-ar", str(SR), w)
        return load(w)
    raise ValueError("нет источника " + spec["engine"])


_mtl, _refcache = None, {}
_silma, LAST = None, {}


def silma_ref():
    """Образец для SILMA: silma-ref-voice-commercial.wav (разрешён для коммерции; путь — SILMA_REF), не длиннее 7,9 с
    (иначе SILMA режет его сама и зовёт свой распознаватель), и его текст — по faster-whisper."""
    src = os.environ.get("SILMA_REF") or os.path.expanduser("~/silma_ref.wav")
    a = load(src)
    if len(a) > 7.9 * SR:
        fr = SR // 50
        lo, hi = int(5.5 * SR) // fr, int(7.9 * SR) // fr
        e = [rms(a[k * fr:(k + 1) * fr]) for k in range(lo, hi)]
        cut = (lo + int(np.argmin(e))) * fr + fr // 2
        a = a[:cut]
    p = os.path.join(TMP, "silma_ref.wav")
    save(a, p)
    txt = heard(a, "ar", "fw:large-v3-turbo")
    log("образец SILMA:", round(len(a) / SR, 2), "с —", txt)
    return p, txt


def silma(text, spec):
    import json as _json
    global _silma
    if _silma is None or _silma[0].poll() is not None:
        ref, ref_text = silma_ref()
        py = os.environ.get("SILMA_PY") or os.path.expanduser("~/silma/bin/python")
        srv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "silma_srv.py")
        p = subprocess.Popen([py, srv], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        ready = p.stdout.readline()
        if '"ready"' not in ready:
            raise RuntimeError("SILMA не запустилась: " + ready[:200])
        _silma = (p, ref, ref_text)
    p, ref, ref_text = _silma
    out = os.path.abspath(os.path.join(TMP, "silma_out.wav"))
    q = {"text": text, "out": out, "ref": os.path.abspath(ref), "ref_text": ref_text, "speed": spec.get("speed", 1.0),
         "nfe": spec.get("nfe", 32), "seed": spec.get("seed", 1234), "tashkeel": spec.get("tashkeel", True)}
    p.stdin.write(_json.dumps(q, ensure_ascii=False) + "\n")
    p.stdin.flush()
    ans = _json.loads(p.stdout.readline() or '{"ok": false, "error": "сервер SILMA упал"}')
    if not ans.get("ok"):
        raise RuntimeError("SILMA: " + str(ans.get("error")))
    LAST.clear()
    LAST.update(tk=ans.get("tk"), sec=ans.get("sec"))
    return load(out)


def spec_ref(spec):
    """Образец для Chatterbox Multilingual: готовый файл spec['ref'] или фраза голосом Piper spec['ref_piper']."""
    if spec.get("ref"):
        return spec["ref"]
    if spec.get("ref_default"):      # встроенный голос модели (MIT) — когда свободного родного голоса-образца для языка нет (арабский)
        return None
    key = spec["ref_piper"]
    if key not in _refcache:
        text = spec.get("ref_text") or "Heute ist ein schöner Tag. Die Kinder spielen draußen im Schnee und lachen laut."
        a = piper(text, key, 0.95)
        p = os.path.join(TMP, "mtlref_" + os.path.basename(key) + ".wav")
        save(a, p)
        _refcache[key] = p
    return _refcache[key]


def mtl(text, lang, ref, speed=1.0, cfg=0.5, exag=0.5):
    global _mtl
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS as M
    if _mtl is None:
        try:
            _mtl = call_kw(M.from_pretrained, device="cpu", t3_model="v3")
        except Exception:
            traceback.print_exc()
            _mtl = M.from_pretrained(device="cpu")
    kw = dict(text=text, language_id=lang, exaggeration=exag, cfg_weight=cfg, temperature=0.8)
    if ref:
        kw["audio_prompt_path"] = ref
    w = call_kw(_mtl.generate, **kw)
    a = resample(to_np(w), _mtl.sr)
    return tempo(a, speed) if abs(speed - 1.0) > 0.01 else a


# ---------- перекраска ----------
_vc = None


def vc(src_arr, ref_path):
    global _vc
    from chatterbox.vc import ChatterboxVC
    if _vc is None:
        _vc = call_kw(ChatterboxVC.from_pretrained, device="cpu")
        log("VC загружен, sr", _vc.sr)
    p = os.path.join(TMP, "vc_src.wav")
    save(src_arr, p)
    w = call_kw(_vc.generate, audio=p, target_voice_path=ref_path)
    return resample(to_np(w), _vc.sr)


def render(text, spec, ref_path, f0_ref, pre=None, post=True, thr=1.5):
    """Фраза голосом героя. pre={'f0':..,'F':..} — подъём высоты источника до перекраски."""
    t0 = time.time()
    s = source(text, spec)
    if pre:
        s = change(s, f0=pre.get("f0", 0), F=pre.get("F", 1.0), rng=pre.get("range", 1.0))
    raw = vc(s, ref_path)
    out, shift = match_pitch(raw, f0_ref, thr) if post else (raw, 0.0)
    return trim(out), {"shift_st": shift, "sec": round(time.time() - t0, 1)}


# ---------- проверки ----------
_enc, _wh = None, {}


def embed(arr):
    global _enc
    import torchaudio
    if _enc is None:
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except Exception:
            from speechbrain.pretrained import EncoderClassifier
        _enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                              savedir=os.path.join(TMP, "ecapa"), run_opts={"device": "cpu"})
    x = torchaudio.functional.resample(torch.tensor(np.asarray(arr, dtype=np.float32)).unsqueeze(0), SR, 16000)
    with torch.no_grad():
        e = _enc.encode_batch(x).reshape(-1)
    return (e / e.norm()).numpy()


def heard(arr, lang, size="small"):
    """Что услышал распознаватель. size: 'small' (openai-whisper) или 'fw:large-v3-turbo' (faster-whisper, точнее, нужен для хинди)."""
    p = os.path.join(TMP, "wh.wav")
    save(arr, p)
    if size.startswith("fw:"):
        from faster_whisper import WhisperModel
        if size not in _wh:
            _wh[size] = WhisperModel(size[3:], device="cpu", compute_type="int8")
        segs, _ = _wh[size].transcribe(p, language=lang, beam_size=5, vad_filter=False)
        return " ".join(s.text.strip() for s in segs).strip()
    import whisper
    if size not in _wh:
        _wh[size] = whisper.load_model(size)
    return _wh[size].transcribe(p, language=lang, fp16=False)["text"].strip()


def norm_chars(t):
    """Для сравнения по буквам: без знаков препинания и пробелов; деванагари — без нукты, чандрабинду как анусвара."""
    import unicodedata
    t = unicodedata.normalize("NFC", t.lower())
    t = t.replace("\u093c", "").replace("\u0901", "\u0902")
    # арабский: без огласовок и растяжки; алиф с хамзой/маддой = алиф, алиф максура = йа, та марбута = ха, хамза на вав/йа = вав/йа
    t = re.sub("[\u064b-\u0652\u0670\u0640]", "", t)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي"), ("ء", "")):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalnum())


def char_pct(ref, hyp):
    """Доля совпавших букв (для языков, где написание слова «плавает», например хинди)."""
    r, h = norm_chars(ref), norm_chars(hyp)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    return round(100.0 * sum(b.size for b in sm.get_matching_blocks()) / max(1, len(r)), 1)


def words(t):
    return re.findall(r"\w+", t.lower())


def clear_pct(ref, hyp):
    r, h = words(ref), words(hyp)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    ok = sum(b.size for b in sm.get_matching_blocks())
    extra = max(0, len(h) - ok)
    return round(100.0 * ok / max(1, len(r)), 1), extra


def edge_label(text, path, voice="ru-RU-SvetlanaNeural"):
    try:
        w = source(text, {"engine": "edge", "voice": voice})
        save(w, path)
        return True
    except Exception:
        traceback.print_exc()
        return False
