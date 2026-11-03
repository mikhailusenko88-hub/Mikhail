# «Неоновый луг» с калибровкой (артефакт claude.ai, версия 1793748785)

Проектор луга со шмелём, «Стало/Было» против кадра трассировки, кнопка «Калибровка».
Калибровка — поправка каждого диода по трассировщику Honeycomb, `calib.js` = `calib.bin`.
Порядок: подряд образцы травы 0–9, земля, у каждого дерева ствол и листва, по 3 байта на вершину; 128 — без поправки.
В шейдере поправка считается как `exp2((aCal·255 − 128) / 64)`.

Данные сцены собирает завод:
```
cd ../../zavod && g++ -O3 -march=native -ffast-math -fopenmp -DLEAFN=6 -o neon_bake neon_bake.cpp
mkdir -p web && ./neon_bake web        # web/scene.bin + web/frames.bin (~2 с); frames.bin совпадает с артефактом байт в байт
cp web/scene.bin web/frames.bin ../neon/lug/
```
Без `scene.js`/`frames.js` страница сама берёт `scene.bin`/`frames.bin` рядом с собой. Открывать с http (`python3 -m http.server`).
