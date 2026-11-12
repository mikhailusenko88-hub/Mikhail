#!/usr/bin/env python3
"""Свои голоса «ничьи» (12.11.2026) для модели Silero v5 CIS: ru_nash1 (спокойный), ru_nash2 (живее), ru_nash3 (моложе).
Голос — смесь отпечатков нескольких мужских дикторов той же модели (лицензия MIT), подогнанная по силе к обычному диктору.
Отпечатки лежат в voices.json (три таблицы: длительности, высоты, основная). Вписываются на место дикторов-двойников
на других языках (bak_/tat_/erz_…), которые бот не использует, и получают свои имена.

  import nash_voices; nash_voices.apply(model, "voices.json")   — после загрузки модели (torch.package)
"""
import json

# места для своих голосов: дикторы-двойники на других языках (ru_-версии остаются как были)
# подобраны с близким размахом высоты (mean_std_coef 3,62 / 3,74 / 3,29 при наших 3,64 / 3,77 / 3,29) — если поправить его не выйдет
SLOTS = ["bak_miyau", "kat_vika", "ukr_igor"]


def _close(a, b, tol=1e-4):
    return len(a) == len(b) and max(abs(float(x) - float(y)) for x, y in zip(a, b)) < tol


def apply(model, path, log=print):
    import torch
    V = json.load(open(path, encoding="utf-8"))
    pack = model.packages[0]
    jm = pack.models[0]
    ids = pack.speaker_to_ids[0]
    a = ids["ru_albina"]
    tables = {
        "dp.spe.weight": jm.dur_predictor.dur_pred.speaker_embedding.weight,
        "pp.spe.weight": jm.pitch_predictor.pitch_pred.speaker_embedding.weight,
        "spe.weight": jm.tacotron.speaker_embedding.weight,
    }
    fp = V["fingerprint"]["ru_albina"]
    for n, t in tables.items():      # та ли это модель: строка Альбины совпадает с телефонной
        if not _close(t[a].tolist(), fp[n]):
            raise RuntimeError(f"таблица {n} не совпадает с отпечатком Альбины — другая модель")
    coef = getattr(jm, "mean_std_coef", None)
    names = []
    with torch.no_grad():
        for slot, (name, v) in zip(SLOTS, V["voices"].items()):
            sid = ids[slot]
            for n, t in tables.items():
                t[sid].copy_(torch.tensor(v["rows"][n], dtype=t.dtype))
            if coef is not None:
                try:
                    coef[sid] = v["coef"]
                except Exception as e:      # высота «high/low» в SSML без поправки — почти так же
                    log(f"свои голоса: высоту для {name} не поправил ({e})")
            ids[name] = sid
            for lst in (getattr(model, "speakers", None), getattr(pack, "speakers", None)):
                if isinstance(lst, list) and name not in lst:
                    lst.append(name)
            names.append(name)
    log("свои голоса подключены: " + ", ".join(names))
    return names
