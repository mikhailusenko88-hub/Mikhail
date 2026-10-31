# Проверка мультиков без iPhone

Нужно: `npm i playwright` (в среде Claude Chromium уже есть) и three.js в `Resources/Mebel` — как в CI:
`npm pack three@0.169.0 && tar xzf three-0.169.0.tgz && cp package/build/three.module.min.js Resources/Mebel/`

- `node render.js halloween.txt 5 30 120` — разобрать сценарий (или серию .json) и снять кадры на 5-й, 30-й, 120-й секунде.
- `node render.js halloween.txt --hq --out=kadry 30` — то же в режиме «как в кино» (медленно, до 2–3 мин на кадр).
- `node sheet.js` / `node sheet.js hq` — все предметы на одном листе.

Озвучку голосом iPhone и запись смеха здесь проверить нельзя — только на телефоне.
