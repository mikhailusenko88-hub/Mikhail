"""Звук -> текст с отметками времени. Текст пишется только в файл (в журнал ничего не выводится).
Запуск: python whisper_run.py <звук> <текст.txt> <сведения.txt>
В сведения попадают только цифры: модель, длительность, число фраз, время работы."""
import sys, time

src, out, info = sys.argv[1], sys.argv[2], sys.argv[3]
from faster_whisper import WhisperModel

t0 = time.time()
model, name = None, ""
for name in ("large-v3-turbo", "turbo", "medium"):
    try:
        model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=4)
        break
    except Exception as e:
        sys.stderr.write("модель %s не загрузилась: %s\n" % (name, str(e)[:120]))
if model is None:
    sys.exit(2)

segments, meta = model.transcribe(
    src, language="ru", beam_size=5, vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=400),
    condition_on_previous_text=False,
    initial_prompt="Разговор продавца с менеджером поддержки Авито: объявления, тариф, лимит контактов, продвижение, автозагрузка, доставка, отзывы.",
)
n = 0
with open(out, "w", encoding="utf-8") as f:
    for s in segments:
        text = s.text.strip()
        if not text:
            continue
        f.write("[%02d:%02d] %s\n" % (int(s.start) // 60, int(s.start) % 60, text))
        n += 1
with open(info, "w", encoding="utf-8") as f:
    f.write("model=%s duration=%.0f segments=%d seconds=%.0f\n" % (name, meta.duration, n, time.time() - t0))
