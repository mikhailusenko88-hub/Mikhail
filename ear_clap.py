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


def main():
    torch.set_num_threads(4)
    model = ClapModel.from_pretrained(M).eval()
    proc = ClapProcessor.from_pretrained(M)
    scale = float(model.logit_scale_t.exp())
    temb = {}
    with torch.no_grad():
        for sname, d in SETS.items():
            tok = proc.tokenizer(list(d.values()), padding=True, return_tensors="pt")
            e = model.get_text_features(**tok)
            temb[sname] = torch.nn.functional.normalize(e, dim=-1)
    os.makedirs("out", exist_ok=True)
    for line in open(sys.argv[1]):
        path = line.strip()
        if not path:
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        print("==", name, flush=True)
        x = load48(path)
        W, H = 10 * 48000, 5 * 48000
        starts = list(range(0, max(1, len(x) - W + H), H)) or [0]
        chunks = [x[s:s + W] for s in starts]
        chunks = [c for c in chunks if len(c) > 3 * 48000]
        with torch.no_grad():
            feats = proc.feature_extractor(chunks, sampling_rate=48000, return_tensors="pt")
            ae = model.get_audio_features(**feats)
            ae = torch.nn.functional.normalize(ae, dim=-1)
        R = {"file": os.path.basename(path), "win_start_s": [s / 48000 for s in starts[:len(chunks)]], "win_s": 10, "sets": {}}
        for sname, d in SETS.items():
            logits = scale * ae @ temb[sname].T
            p = torch.softmax(logits, dim=-1).numpy()
            R["sets"][sname] = {"labels": list(d), "mean": p.mean(0).round(4).tolist(), "series": p.round(3).tolist()}
        json.dump(R, open(f"out/{name}.clap.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
