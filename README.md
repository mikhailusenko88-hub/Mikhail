# Ролики-цитаты «Живые строки»
Движок: акварельная сцена рисуется сама, поверх — цитата (рус + англ), автор; оркестровая музыка генерируется.
- `schedule_30d.json` — план на 30 дней (90 роликов по 3 цитаты).
- `python3 render_day.py N` — рендер дня N в `out/`.
- Поменять `render.txt` и запушить в ветку `quotes` — GitHub Actions отрендерит дни 2–30 параллельно, каждый день — в ветку `quotes-out-dXX`.
Шрифты: Prata, Cormorant Garamond, PT Serif (SIL Open Font License, `fonts/OFL.txt`).
