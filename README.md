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

## Лягушка (H24, 16.11.2026) — старт «уже в деле», текст как у лучших роликов канала
    gcc -O2 -o sim_frog sim_frog.c -lm
    ./sim_frog sim_frog.bin events_frog.txt 3 0.9 900 0 11 30 1200 10.5 1.6 4.8 120   # последний аргумент — шариков на старте
    python3 render_frog.py out.mp4                                                    # 14 с

## Медведь с музыкой (H27, 18.11.2026) — своя мелодия, шарики рождаются на каждую восьмую
    python3 music_bear.py bear_music.wav bear_notes.txt          # мелодия: 2 круга с ускорением, мажор на «пыке»
    python3 ../ear/studio/enc.py bear_music.wav bear_music.m4a -14   # −14 LUFS (ветка muzyka-sluh)
    gcc -O2 -o sim_bear sim_bear.c -lm
    ./sim_bear sim_bear.bin events_bear.txt 3 0.9 900 0 11 30 1140 18.25 1.3 8.5 120 bear_grid.txt   # роды только на сетке восьмых
    python3 render_bear.py out.mp4                                # 16,6 с, звук из bear_music.m4a
«Уши» (ветка muzyka-sluh, medved_krug_v2): плач 26, свет 61, CLAP радость 0,41 / меланхолия 0,40, шипение −89 дБ, плотность 0,00001.
