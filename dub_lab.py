# Пробы перекраски (вариант 2, выбран Михаилом 22.11.2026): разные настройки на одних и тех же фразах.
# Читает lab.json, пишет out_lab/v/<key>.mp3, out_lab/labels/*.wav (подписи), out_lab/report.md и report.json.
import json, os, sys, traceback

import numpy as np

import dubcore as D

CFG = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "lab.json", encoding="utf-8"))
OUT = CFG.get("out", "out_lab")
for d in (OUT, os.path.join(OUT, "v"), os.path.join(OUT, "labels")):
    os.makedirs(d, exist_ok=True)
NAMES = CFG["names"]
REFS = {s: f"refs/{s}_ref.wav" for s in NAMES}
REFS.update(CFG.get("refs", {}))


def main():
    ref_arr = {s: D.load(REFS[s]) for s in NAMES}
    ref_f0 = {s: D.measure(a)["f0"] for s, a in ref_arr.items()}
    D.log("высота образцов", ref_f0)
    rows, E = [], {}
    for job in CFG["jobs"]:
        row = {k: job.get(k) for k in ("key", "hero", "lang", "note")}
        try:
            ref = job.get("ref") or REFS[job["hero"]]
            f0 = job.get("f0") or ref_f0[job["hero"]]
            pieces, shifts, secs = [], [], 0.0
            for line in job["lines"]:
                a, info = D.render(line, job["src"], ref, f0, pre=job.get("pre"), post=job.get("post", True))
                pieces += [a, D.silence(0.45)]
                shifts.append(info["shift_st"])
                secs += info["sec"]
            arr = np.concatenate(pieces)
            p = os.path.join(D.TMP, "lab.wav")
            D.save(arr, p)
            norm = os.path.join(D.TMP, "lab_n.wav")
            D.ff("-i", p, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(D.SR), "-ac", "1", norm)
            arr = D.load(norm)
            D.ff("-i", norm, "-codec:a", "libmp3lame", "-q:a", "3", os.path.join(OUT, "v", job["key"] + ".mp3"))
            m = D.measure(arr)
            row.update(m, shift=shifts, synth_sec=round(secs, 1), dur=round(len(arr) / D.SR, 1))
            txt = D.heard(arr, job["lang"], CFG.get("whisper", "small"))
            row["heard"] = txt
            row["clear"], row["extra"] = D.clear_pct(" ".join(job["lines"]), txt)
            try:
                if not E:
                    E.update({s: D.embed(a) for s, a in ref_arr.items()})
                e = D.embed(arr)
                sims = {s: float(e @ E[s]) for s in NAMES}
                row["sim"] = round(sims[job["hero"]], 3)
                row["nearest"] = max(sims, key=sims.get)
                row["other"] = round(max(v for s, v in sims.items() if s != job["hero"]), 3)
            except Exception:
                traceback.print_exc()
            D.log(job["key"], "понято", row["clear"], "лишних", row["extra"], "сходство", row.get("sim"), "f0", row.get("f0"))
        except Exception as ex:
            traceback.print_exc()
            row["error"] = f"{type(ex).__name__}: {ex}"[:300]
        rows.append(row)

    for name, text in CFG.get("labels", {}).items():
        D.edge_label(text, os.path.join(OUT, "labels", name + ".wav"))

    json.dump({"ref_f0": ref_f0, "rows": rows}, open(os.path.join(OUT, "report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    md = ["# Пробы перекраски", "", "| Ключ | Заметка | Понято | Лишних слов | Сходство | Ближе всего | Чужой | f0 | HNR | Сдвиг, пт | Синтез, с | Услышано |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            md.append(f"| {r['key']} | {r.get('note') or ''} | ОШИБКА | | | | | | | | | {r['error']} |")
        else:
            md.append(f"| {r['key']} | {r.get('note') or ''} | {r.get('clear')}% | {r.get('extra')} | {r.get('sim')} | "
                      f"{NAMES.get(r.get('nearest'), '')} | {r.get('other')} | {r.get('f0')} | {r.get('hnr')} | {r.get('shift')} | "
                      f"{r.get('synth_sec')} | {r.get('heard')} |")
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    D.log("готово")


if __name__ == "__main__":
    main()
