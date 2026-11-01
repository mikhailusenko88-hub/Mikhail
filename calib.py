#!/usr/bin/env python3
# Калибровка «слуха»: озвучиваем фразы с ИЗВЕСТНЫМИ ударениями (правильными и нарочно сдвинутыми)
# несколькими голосами Silero и сохраняем признаки гласных → out/calib.json (для подбора весов).
import json, os, re
import numpy as np
import voice_check as vc
import gen

SENT = [
    "Сутки на Венере длятся дольше, чем год на этой планете.",
    "Самое глубокое озеро в мире находится в Сибири.",
    "Пчелы умеют узнавать человеческие лица.",
    "Осьминог имеет три сердца и голубую кровь.",
    "Молния нагревает воздух сильнее, чем поверхность солнца.",
    "Улитка может проспать почти три года подряд.",
    "Бананы растут на огромной траве, а не на дереве.",
    "Первый компьютер весил больше двадцати тонн.",
    "Жирафы спят всего несколько минут в сутки.",
    "Медведи узнают знакомые запахи за много километров.",
]
VOICES = os.environ.get("CALIB_VOICES", "kseniya,aidar,xenia,baya,eugene").split(",")

def marked(text):
    words = vc.tokenize(text)
    vc.accentize(text, words)
    return words

def render(words, shift):
    out, told = [], []
    for i, w in enumerate(words):
        e = w["exp"]
        n = len(w["vows"])
        if n >= 2 and e is not None and shift and "ё" not in w["w"]:
            e = (e + 1) % n
        told.append(e)
        if n >= 2 and e is not None:
            k = -1; s = ""
            for c in w["w"]:
                if c in vc.VOW:
                    k += 1
                    if k == e:
                        s += "+"
                s += c
            out.append(s + w["punct"])
        else:
            out.append(w["w"] + w["punct"])
    return " ".join(out), told

data = []
m = gen.silero_model()
for si, text in enumerate(SENT):
    base = marked(text)
    for shift in (False, True):
        t, told = render(base, shift)
        for spk in VOICES:
            try:
                a = m.apply_tts(text=t, speaker=spk, sample_rate=48000, put_accent=True, put_yo=True)
                gen.save_wav(a.numpy(), "tmp_calib.wav")
                audio = vc.load16("tmp_calib.wav")
                words = vc.tokenize(t)
                vowels, P = vc.extract(audio, words)
                for w, tl in zip(words, told):
                    if len(w["vows"]) < 2 or not w.get("map_ok"):
                        continue
                    data.append({"s": si, "shift": shift, "spk": spk, "w": w["w"], "told": tl,
                                 "vf": [{k: v.get(k) for k in ("k", "L", "I", "F", "D", "Dn", "dF", "pt")} for v in w["vf"]]})
                print("ok", si, shift, spk, flush=True)
            except Exception as e:
                print("fail", si, shift, spk, repr(e), flush=True)
os.makedirs("out", exist_ok=True)
json.dump(data, open("out/calib.json", "w", encoding="utf-8"), ensure_ascii=False, default=float)
print("слов:", len(data))
