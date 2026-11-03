# Барсик «неоновая основа» для «Мультиков»

Каждый волосок Барсика светится своим заранее посчитанным светом: свет запекается один раз (C++), в телефоне
досчитываются только блики, туман и свет места. Шарф — вязаный: два оборота по шее, узел сбоку, два конца с кисточками,
петли-«косички» в шейдере и ~12 тыс. шерстяных ворсинок (область 12) со своим светом.

В приложении: `Resources/Mebel/multik-barsik.js` + данные `Resources/Mebel/barsik/barsik_data.js` (14 МБ, gzip+base64).
В режиме «как в кино» любой герой-кот по имени «Барсик» рисуется этим мехом; обычный Барсик остаётся невидимым скелетом
(поза из `applyPose`, руки для предметов, тень — слой 1, его видит только камера теней). Свет — от места мультика
(солнце, контровой, небо/земля), запечённые каналы: 0 солнце, 1 контровой, 2 мягкий спереди, 4 небо, 5 земля.

Пересборка данных (нужны numpy, scipy, scikit-image, g++):
```
python3 build_geo_paws.py --var=s2     # форма с лапками-пальчиками (образец 6.2), кожа, мех (out/geo_s2.npz); без пальцев — build_geo.py
python3 add_tau.py s2
python3 knit_scarf.py                  # новый шарф + ворсинки → out/geo_s3.npz (--preview — быстрый вид формы)
python3 add_tau.py s3 && python3 export_geo.py s3
g++ -O3 -march=native -ffast-math -fopenmp -o fur_exp fur.cpp
./fur_exp tauk=0.35 geo=out/geo_s3 bake=out/bake_s3.bin export=out/phone_s3.raw    # ~1 мин на 2 ядрах
RAW=out/phone_s3.raw KNIT=1 python3 pack_phone.py 230000                       # → Resources/Mebel/barsik/barsik_data.js
```
Числа шарфа (кольца, узел, концы, кисточки, ROWH/COLW/NR/NC) — в `knit_scarf.py` и в `KNIT` внутри `multik-barsik.js`: менять вместе.
Проверка без телефона: `node tools/multik/test/render.js сценарий.txt --hq 3 6` (frame.html сам грузит данные Барсика).

## БАРС: лучший Барсик (ноябрь 2026)
- Лапки с пальцами и розовыми подушечками — `build_geo_paws.py` (функции `toe_paw` из `tools/multik/obrazec/heroes/hero_common.py`): подушечки — область 8 ниже 0,42 м (в телефоне идут за лапой, `extraW`), на пальцах шерсть короче (×0,42).
- Налёт (из «неона» v4): `VS_SHELL`/`FS_SHELL` в `multik-barsik.js` — кожа ещё 6 раз слоями до 16 мм внутри шерсти; сила `MKBarsik.shellU.value` (0 — выключить).
