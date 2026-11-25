#!/usr/bin/env python3
"""Свои голоса в модели движка мультика (ONNX, ветка multik-voice → multik-voice-svoy).

Движок выбирает диктора номером; строки голоса (ритм dp, мелодия pp, тембр spe) зашиты таблицами в front.onnx и enc.onnx.
Вписываем наши строки (находки sluh_opt.py / sluh_man.py) на место неиспользуемых дикторов-двойников и даём им имена
в tts.json (svoy_barsik, svoy_ron …) — движок менять не нужно, паспорт героя: speaker=svoy_barsik.

  python onnx_svoy.py <папка voice из multik-voice> <куда>      голоса — cast10/svoy_voices.json
"""
import json, os, shutil, sys
import numpy as np

log = lambda *a: print(*a, flush=True)


def main(src, dst):
    import onnx
    from onnx import numpy_helper
    import svoy2
    V = json.load(open("cast10/svoy_voices.json", encoding="utf-8"))["voices"]
    tts = json.load(open(f"{src}/tts.json", encoding="utf-8"))
    net = svoy2.Net(svoy2.CIS)
    tabs = {role: t.detach().double().numpy() for k, (role, t) in net.tabs.items()}
    order_ok = all(net.ids.get(s) == i for s, i in tts["speakers"].items())
    log("порядок дикторов в torch и в движке совпадает:", order_ok)
    os.makedirs(dst, exist_ok=True)
    found = {}
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".onnx") or fn in ("voc.onnx", "homo.onnx"):
            continue
        m = onnx.load(f"{src}/{fn}")
        ch = 0
        for init in m.graph.initializer:
            a = numpy_helper.to_array(init)
            if a.ndim == 2 and a.shape[0] == len(tts["speakers"]):
                role = next((r for r, t in tabs.items() if t.shape == a.shape and float(np.abs(t - a).max()) < 1e-4), None)
                log(fn, init.name, a.shape, a.dtype, "→", role)
                if role:
                    a = a.copy()
                    for name, v in V.items():
                        a[tts["speakers"][v["slot"]]] = np.asarray(v[role], dtype=a.dtype)
                    init.CopyFrom(numpy_helper.from_array(a, init.name)); ch += 1
                    found[role] = found.get(role, 0) + 1
        if ch:
            onnx.save(m, f"{dst}/{fn}"); log("записан", fn, "таблиц", ch)
    if sorted(found) != ["dp", "pp", "spe"]:
        raise SystemExit(f"не все таблицы найдены: {found}")
    for name, v in V.items():
        sid = tts["speakers"][v["slot"]]
        tts["speakers"][name] = sid
        if v.get("coef"):
            tts["mean_std_coef"][sid] = float(v["coef"])
        log(name, "→ место", v["slot"], sid, "coef", tts["mean_std_coef"][sid], v.get("note", ""))
    json.dump(tts, open(f"{dst}/tts.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({k: {x: v[x] for x in ("slot", "note", "coef", "passport") if x in v} for k, v in V.items()}, open(f"{dst}/svoy.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
