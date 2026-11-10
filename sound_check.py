#!/usr/bin/env python3
# «Что это за звук»: классификатор AudioSet (AST) для смеха, мяуканья, лая и других звуков героев.
# Вход: snd/*.wav|flac|ogg|mp3. Выход: snd_out/report.md, report.json — чем звук кажется нейросети (смех? речь? кошка?).
import glob, json, os, subprocess, sys
import numpy as np
os.makedirs("snd_out", exist_ok=True)
files = sorted(p for p in glob.glob("snd/*") if p.split(".")[-1].lower() in ("wav", "flac", "ogg", "mp3", "m4a"))
if not files:
    print("нет файлов"); sys.exit(0)
import torch
from transformers import AutoFeatureExtractor, ASTForAudioClassification
name = "MIT/ast-finetuned-audioset-10-10-0.4593"
fe = AutoFeatureExtractor.from_pretrained(name); model = ASTForAudioClassification.from_pretrained(name).eval()
id2 = model.config.id2label
GROUPS = {
    "смех": ["Laughter", "Giggle", "Chuckle, chortle", "Belly laugh", "Snicker", "Baby laughter"],
    "речь": ["Speech", "Child speech, kid speaking", "Narration, monologue", "Conversation", "Female speech, woman speaking", "Male speech, man speaking"],
    "кошка": ["Cat", "Meow", "Purr", "Caterwaul", "Hiss"],
    "собака": ["Dog", "Bark", "Yip", "Howl", "Bow-wow", "Growling", "Whimper (dog)"],
    "мышь/писк": ["Mouse", "Squeak", "Patter", "Rodents, rats, mice"],
    "пение": ["Singing", "Child singing", "Female singing", "Male singing", "Humming", "Yodeling"],
    "плач": ["Crying, sobbing", "Baby cry, infant cry", "Whimper", "Wail, moan"],
    "зевок/вздох": ["Yawn", "Sigh", "Gasp", "Breathing", "Snoring"],
    "чих/кашель": ["Sneeze", "Cough", "Sniff"],
    "птица": ["Bird", "Bird vocalization, bird call, bird song", "Chirp, tweet", "Owl", "Hoot", "Crow", "Caw"],
}
lab2id = {v: k for k, v in id2.items()}
def load16(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()
rep = []
for p in files:
    y = load16(p)
    if len(y) < 1600: continue
    with torch.no_grad():
        x = fe(y, sampling_rate=16000, return_tensors="pt"); pr = torch.sigmoid(model(**x).logits[0]).numpy()
    top = [(id2[int(i)], round(float(pr[i]), 3)) for i in np.argsort(-pr)[:6]]
    g = {k: round(float(max(pr[lab2id[l]] for l in ls if l in lab2id)), 3) for k, ls in GROUPS.items()}
    rep.append({"name": os.path.basename(p), "dur": round(len(y) / 16000, 2), "top": top, "groups": g})
    print(os.path.basename(p), g, top[:3], flush=True)
json.dump(rep, open("snd_out/report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ks = list(GROUPS)
L = ["| файл | длит. | " + " | ".join(ks) + " | похоже на |", "|---|---|" + "---|" * (len(ks) + 1)]
for r in rep:
    L.append(f"| {r['name']} | {r['dur']} | " + " | ".join(str(r['groups'][k]) for k in ks) + " | " + ", ".join(f"{a} {b}" for a, b in r["top"][:3]) + " |")
open("snd_out/report.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
