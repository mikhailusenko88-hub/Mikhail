# Пробы голосом Михаила (его запись приходит зашифрованной, всё выходящее тоже шифруется).
#   А: Chatterbox Multilingual (MIT) — модель говорит голосом по записи; Б: наш голос ru_nash3 → ChatterboxVC (тембр по записи).
import sys, os, time, torch, torchaudio as ta
ref, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
torch.set_num_threads(os.cpu_count() or 4)
T = [("a1", "Привет! Это мой голос, только сказала это за меня нейросеть."),
     ("a2", "Почему у жирафа такая длинная шея? Учёные считают, что так ему проще дотянуться до листьев на высоких деревьях."),
     ("a3", "А ты это знал?")]
t0 = time.time()
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
m = ChatterboxMultilingualTTS.from_pretrained(device="cpu"); print("модель", round(time.time() - t0), "с", flush=True)
for n, t in T:
    t1 = time.time(); w = m.generate(t, language_id="ru", audio_prompt_path=ref)
    ta.save(f"{out}/{n}.wav", w, m.sr); print(n, round(time.time() - t1), "с", flush=True)
    t1 = time.time(); w = m.generate(t, language_id="ru", audio_prompt_path=ref, exaggeration=0.35, cfg_weight=0.3)
    ta.save(f"{out}/{n}_calm.wav", w, m.sr); print(n, "calm", round(time.time() - t1), "с", flush=True)
del m
try:
    from chatterbox.vc import ChatterboxVC
    vc = ChatterboxVC.from_pretrained(device="cpu")
    for n in ("a", "b", "z"):
        w = vc.generate(audio=f"myvoice/src_{n}.mp3", target_voice_path=ref)
        ta.save(f"{out}/vc_{n}.wav", w, vc.sr); print("vc", n, flush=True)
except Exception as e:
    print("VC не вышло:", e, flush=True)
