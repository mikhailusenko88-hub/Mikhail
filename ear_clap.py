"""Слух, часть 2 (CLAP, laion/larger_clap_music): насколько звук похож на словесные описания.
Окна по 10 с с шагом 5 с, внутри каждого набора описаний — доли (softmax). Пишет out/<имя>.clap.json."""
import json
import os
import subprocess
import sys

import numpy as np
import torch
from transformers import ClapModel, ClapProcessor

M = "laion/larger_clap_music"
SETS = {
    "настроение": {
        "плач, скорбь": "sad mournful music, weeping and crying",
        "меланхолия": "melancholic nostalgic wistful music",
        "надежда, светлое": "hopeful uplifting music, warm and bright",
        "радость": "happy joyful cheerful music",
        "покой": "calm peaceful relaxing music",
        "эпика, триумф": "epic triumphant heroic cinematic orchestral music",
        "вдохновение": "inspiring motivational music",
        "нежность": "tender romantic beautiful music",
        "тревога, мрак": "dark tense ominous music",
    },
    "голос": {
        "голос плачет/воет": "a woman wailing and crying, sobbing vocal",
        "голос поёт спокойно": "a woman singing a calm gentle melody",
        "эфирный голос без слов": "ethereal wordless female vocals",
        "хор": "a choir singing",
        "без голоса": "instrumental music without vocals",
    },
    "звучание": {
        "живой оркестр, студия": "high quality studio recording of a real orchestra",
        "синтезатор, MIDI": "cheap synthesizer MIDI music, artificial sound",
        "искажения, шум": "distorted noisy low quality audio",
    },
    "стиль": {
        "музыка к фильму": "cinematic film score",
        "медитация, нью-эйдж": "new age meditation music",
        "поп-песня": "pop song",
        "классика, камерная": "classical chamber music",
        "эмбиент, электроника": "ambient electronic music",
        "фортепиано соло": "solo piano music",
    },
}


def load48(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


MODELS = ["laion/larger_clap_music", "laion/clap-htsat-unfused", "laion/clap-htsat-fused"]


def run_set(model, proc, texts, chunks):
    with torch.no_grad():
        inp = proc(text=texts, audios=chunks, sampling_rate=48000, return_tensors="pt", padding=True)
        return model(**inp).logits_per_audio


def diagnose(model, proc, chunks):
    """проверка, что модель вообще различает описания: разброс логитов между «грустной» и «весёлой» музыкой"""
    with torch.no_grad():
        tok = proc.tokenizer(["sad music", "happy music", "a dog barking", "heavy metal guitar"], padding=True, return_tensors="pt")
        te = torch.nn.functional.normalize(model.get_text_features(**tok), dim=-1)
        fe = proc.feature_extractor(chunks[:3], sampling_rate=48000, return_tensors="pt")
        ae = torch.nn.functional.normalize(model.get_audio_features(**fe), dim=-1)
    print("   logit_scale a/t:", float(model.logit_scale_a.exp()), float(model.logit_scale_t.exp()))
    print("   текст-текст cos:", np.round((te @ te.T).numpy(), 2).tolist())
    print("   звук-текст cos:", np.round((ae @ te.T).numpy(), 3).tolist())
    lg = run_set(model, proc, ["sad music", "happy music", "a dog barking", "heavy metal guitar"], chunks[:3])
    spread = float((lg.max(-1).values - lg.min(-1).values).mean())
    print("   разброс логитов:", round(spread, 3), flush=True)
    return spread


def main():
    torch.set_num_threads(4)
    todo = [ln.strip() for ln in open(sys.argv[1]) if ln.strip()]
    if not todo:
        return
    x0 = load48(todo[0])
    ch0 = [x0[s:s + 480000] for s in range(0, max(1, len(x0) - 144000), 240000)]
    model = proc = None
    for M_ in MODELS:
        print("== модель", M_, flush=True)
        try:
            mdl = ClapModel.from_pretrained(M_).eval()
            prc = ClapProcessor.from_pretrained(M_)
            if diagnose(mdl, prc, ch0) > 1.0:
                model, proc = mdl, prc
                break
        except Exception as e:  # noqa: BLE001
            print("   ошибка", str(e)[:300], flush=True)
    if model is None:
        print("CLAP не различает описания — пропуск", flush=True)
        return
    os.makedirs("out", exist_ok=True)
    for path in todo:
        name = os.path.splitext(os.path.basename(path))[0]
        print("==", name, flush=True)
        x = load48(path)
        starts = [s for s in range(0, max(1, len(x) - 3 * 48000), 5 * 48000)]
        chunks = [x[s:s + 10 * 48000] for s in starts]
        R = {"file": os.path.basename(path), "model": M_, "win_start_s": [s / 48000 for s in starts], "win_s": 10, "sets": {}}
        for sname, d in SETS.items():
            lg = run_set(model, proc, list(d.values()), chunks)
            p = torch.softmax(lg, dim=-1).numpy()
            R["sets"][sname] = {"labels": list(d), "mean": p.mean(0).round(4).tolist(), "series": p.round(3).tolist(),
                                "logit_spread": round(float((lg.max(-1).values - lg.min(-1).values).mean()), 3)}
        json.dump(R, open(f"out/{name}.clap.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
