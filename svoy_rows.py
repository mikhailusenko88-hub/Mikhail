# Строки отпечатков наших свободных смесей (v5_cis, MIT) в формате фермы бота (voices.json ветки pochemu-albina):
# {"voices": {имя: {"desc", "recipe", "coef", "ssml": {"pitch","rate"}, "rows": {"dp.spe.weight","pp.spe.weight","spe.weight"}}}}
import json, os
import svoy, svoy2

log = svoy.log


def main():
    F = json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]
    M = json.load(open("cast9/golos_manera.json", encoding="utf-8"))["voices"]
    todo = [("ru_svoy1", "свободный под №4 (g03) — лучший по замерам", F["ru_svoy1"]["w"]),
            ("ru_manera1", "в манере №4, вариант 1 (ритм alfia)", M["ru_manera1"]["w"]),
            ("ru_manera2", "в манере №4, вариант 2 (ритм nash3, мелодия zinaida)", M["ru_manera2"]["w"])]
    net = svoy2.Net(svoy2.CIS)
    out = {"model": "silero v5_cis_base (MIT)", "made": "2026-11-25",
           "how": "как ru_nash*: строки вписываются на место неиспользуемого диктора (nash_voices.py)", "voices": {}}
    for name, desc, w in todo:
        rows = net.build(w)
        out["voices"][name] = {"desc": desc, "recipe": {"name": name, "w": w}, "coef": rows.get("coef"),
                               "ssml": {"pitch": "low", "rate": "medium"},
                               "rows": {svoy2.ROLE_OF_NASH[role]: [round(float(x), 6) for x in rows[k].tolist()]
                                        for k, (role, _) in net.tabs.items()}}
        log(name, {k: len(v) for k, v in out["voices"][name]["rows"].items()}, "coef", rows.get("coef"))
    # свободные места: дикторы-двойники на других языках (не ru_), с их размахом высоты — чтобы выбрать ближайшее
    slots = {}
    for s, i in net.ids.items():
        if not s.startswith("ru_"):
            try:
                slots[s] = round(float(net.coef[i]), 4)
            except Exception:
                slots[s] = None
    out["slots"] = slots
    os.makedirs("cast9", exist_ok=True)
    json.dump(out, open("cast9/voices_svoy.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("мест:", len(slots), list(slots.items())[:12])


if __name__ == "__main__":
    main()
