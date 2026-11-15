# «Can 1 ball fill the CAT?» — Shorts для Beautiful Shorts (H22, 15.11.2026)

Силуэт заполняется шариками: каждый отскок от стенки рождает новый шарик; на 100% — волна перекрашивает шарики в мордочку, кот моргает и смотрит по сторонам.

    gcc -O2 -o sim2 sim2.c -lm
    ./sim2 sim.bin events.txt 3 0.9 900 0 9 40 2000 10.5 2.0 0.8   # seed P скорость G R maxT NT T97 TL TS
    python3 stats.py events.txt                                    # когда сколько шариков
    python3 render.py out.mp4 - 0.5,6,12.6,15                      # кадры на проверку → /tmp/still_*.jpg
    python3 render.py out.mp4                                      # ролик ~19 с, рендер ~25 с

Новый зверь: силуэт — shape.py и та же SDF в sim2.c; мордочка — picture.py (состояния center/left/right/closed).

## Неоновый вид (H23, 16.11.2026) — как у соседей: чёрный фон, радужные шарики, без текста в кадре
    ./sim2 sim_neon.bin events_neon.txt 3 0.9 900 0 11 40 1300 10.5 2.0 0.8   # шарики крупнее: R=11, 1 300 шт.
    python3 render_neon.py out.mp4
