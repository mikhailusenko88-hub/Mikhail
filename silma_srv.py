# Сервер SILMA TTS для арабского дубляжа (26.11.2026). Запускается в отдельном окружении (~/silma), чтобы не мешать Chatterbox.
# Лицензии (сверено 26.11 по github.com/SILMA-AI/silma-tts): код MIT, веса Apache-2.0; образец голоса — только
# silma-ref-voice-commercial.wav (образец «по умолчанию» ar.ref.24k.wav коммерчески использовать НЕЛЬЗЯ).
# Огласовки — CATT (abjadai/catt, Apache-2.0 с 2025 г.).
# Протокол: на вход строки JSON {text, out, ref, ref_text, speed, nfe, seed, tashkeel, fix}; на выход одна строка JSON на запрос.
import json, os, re, sys, time, traceback, types

ANS = os.fdopen(os.dup(1), "w", buffering=1)   # ответы — в настоящий stdout
os.dup2(2, 1)                                   # всё, что печатает SILMA, — в stderr
sys.stdout = sys.stderr

# NeMo (нормализация чисел) не ставим — числа в переводе пишем словами. Заглушка, чтобы модуль SILMA импортировался.
for name in ("nemo_text_processing", "nemo_text_processing.text_normalization",
             "nemo_text_processing.text_normalization.normalize"):
    sys.modules[name] = types.ModuleType(name)


class _NoNormalizer:
    def __init__(self, *a, **k):
        raise RuntimeError("NeMo не установлен — числа писать словами")


sys.modules["nemo_text_processing.text_normalization.normalize"].Normalizer = _NoNormalizer

import torch  # noqa: E402

torch.set_num_threads(max(1, os.cpu_count() or 4))
from silma_tts.api import SilmaTTS  # noqa: E402
import silma_tts.infer.utils_infer as U  # noqa: E402

tts = SilmaTTS(enable_normalizer=False, force_tashkeel=True, device="cpu")
ANS.write(json.dumps({"ready": True}) + "\n")

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        q = json.loads(line)
        t0 = time.time()
        text = q["text"]
        tk = text
        if q.get("tashkeel", True) and U.text_is_arabic(text) and not U.text_has_tashkeel(text):
            tk = re.sub(U.arabic_sentence_with_punct, lambda m: U.tashkeel_model.do_tashkeel(m.group(0)), text)
        wav, sr, _ = tts.infer(ref_file=q["ref"], ref_text=q["ref_text"], gen_text=tk,
                               speed=float(q.get("speed", 1.0)), nfe_step=int(q.get("nfe", 32)),
                               fix_duration=q.get("fix"), seed=int(q.get("seed", 1234)),
                               normalize_numbers=False, force_tashkeel=False, file_wave=q["out"],
                               show_info=lambda *a, **k: print(*a, file=sys.stderr))
        ANS.write(json.dumps({"ok": True, "sr": sr, "tk": tk, "sec": round(time.time() - t0, 1)}, ensure_ascii=False) + "\n")
    except Exception as ex:
        traceback.print_exc()
        ANS.write(json.dumps({"ok": False, "error": f"{type(ex).__name__}: {ex}"[:300]}, ensure_ascii=False) + "\n")
