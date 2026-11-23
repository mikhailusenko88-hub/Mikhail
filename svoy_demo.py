#!/usr/bin/env python3
"""Пробные выпуски «Почему так?» голосом №4 (24.11.2026, Михаил: «пришли озвучку… как скажут „а ты это знал“»).
Строки — настоящие из банка бота (ветка golos, stage_bank.json), сложены в 4 выпуска. Каждая строка озвучивается отдельно,
как на ферме, ударения в омографах — по словарю ruaccent (svoy_omo), остальное модель v5_ru ставит сама.
  python svoy_demo.py      → cast6/pochemu_demo.mp3, cast6/konczovka.mp3, cast6/demo.md
"""
import json, os, re, shutil, subprocess
import numpy as np
import svoy, svoy2, svoy_bars, svoy_omo

SCRIPTS = [
    ["Верблюд хранит воду в горбу?", "Это миф.", "В горбу жир — запас еды на недели.",
     "Воду верблюд запасает в крови: он выпивает сто литров за десять минут.",
     "А его кровяные клетки не лопаются от такого объёма.", "А ты это знал?"],
    ["Самое громкое животное на планете живёт в океане.", "Кашалот.", "Его щелчки громче взлетающего самолёта.",
     "Такой звук может оглушить водолаза.", "Так кашалот находит добычу в полной темноте.", "А ты это знал?"],
    ["Самый дорогой материал в мире — не золото и не алмаз.", "Это антиматерия.",
     "Грамм стоил бы десятки триллионов долларов.", "За всю историю её получили меньше одной миллиардной грамма.",
     "При встрече с обычным веществом она взрывается.", "А ты это знал?"],
    ["Самое холодное место во Вселенной — на Земле.", "В лаборатории.",
     "Учёные охлаждают атомы почти до абсолютного нуля.", "Это холоднее открытого космоса.", "А ты это знал?"],
]
GAP, GAP_SCRIPT = 0.45, 1.6


def main():
    os.makedirs("cast6", exist_ok=True); os.makedirs("tmp", exist_ok=True)
    svoy_omo.ruacc()
    svoy2.patch_ruaccent()
    net = svoy2.Net(svoy2.RU)
    rows = net.build(svoy_bars.W4); net.put(rows)
    sp = svoy2.SLOT[svoy2.RU]
    import gen as g
    rep, seq = ["# Пробные выпуски «Почему так?» голосом №4", ""], []

    def say(line, path):
        t = re.sub(r"\s+—\s+", ", ", line)          # тире модель не слышит — запятая
        t = svoy_omo.omo_marks(t)[0]
        a = net.m.apply_tts(text=t, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
        g.save_wav(a.numpy() if hasattr(a, "numpy") else a, path)
        return t

    for si, sc in enumerate(SCRIPTS):
        rep += [f"## Выпуск {si + 1}", ""]
        for li, line in enumerate(sc):
            p = f"tmp/s{si}_{li}.wav"
            sent = say(line, p)
            r = svoy2.light(p, line)
            flag = "" if r["match"] >= 0.9 else f" ⚠ слышно «{r['heard'].strip()}»"
            rep.append(f"- {sent} — UTMOS {r['utmos']:.2f}{flag}")
            seq.append(p)
            seq.append("GAP" if li < len(sc) - 1 else "GAPS")
        rep.append("")
    # концовки для сравнения: как говорит модель / с нашей мелодией вопроса (как в боте с 8 ноября)
    ends = []
    for k, line in enumerate(["А ты это знал?", "Верблюд хранит воду в горбу?"]):
        p0, p1 = f"tmp/e{k}_0.wav", f"tmp/e{k}_1.wav"
        say(line, p0); shutil.copy(p0, p1)
        try:
            g.qvrise(p1)
        except Exception as e:
            svoy.log("мелодия не легла:", repr(e))
        ends += [p0, "GAP", p1, "GAPS"]
    open("cast6/demo.md", "w", encoding="utf-8").write("\n".join(rep) + "\n")
    svoy.log("\n".join(rep))
    for name, s in (("pochemu_demo", seq), ("konczovka", ends)):
        sil = {"GAP": GAP, "GAPS": GAP_SCRIPT}
        cmd, fc, n = ["ffmpeg", "-v", "error", "-y"], "", 0
        for x in s:
            if x in sil:
                cmd += ["-f", "lavfi", "-t", str(sil[x]), "-i", "anullsrc=r=48000:cl=mono"]
            else:
                cmd += ["-i", x]
            fc += f"[{n}:a]aresample=48000,aformat=channel_layouts=mono[x{n}];"; n += 1
        fc += "".join(f"[x{j}]" for j in range(n)) + f"concat=n={n}:v=0:a=1,{svoy.SOFT}[o]"
        subprocess.run(cmd + ["-filter_complex", fc, "-map", "[o]", "-ac", "1", "-ar", "48000", "-c:a", "libmp3lame",
                              "-b:a", "160k", f"cast6/{name}.mp3"], check=True)
        svoy.log(name, os.path.getsize(f"cast6/{name}.mp3"))


if __name__ == "__main__":
    main()
