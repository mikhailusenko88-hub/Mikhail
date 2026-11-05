# Ролики-цитаты «Живые строки»
Движок: акварельная сцена рисуется сама, поверх — цитата (рус + англ), автор; оркестровая музыка генерируется.
- `schedule_30d.json` — план на 30 дней (90 роликов по 3 цитаты).
- `python3 render_day.py N` — рендер дня N в `out/`.
- Поменять `render.txt` и запушить в ветку `quotes` — GitHub Actions отрендерит дни 2–30 параллельно, каждый день — в ветку `quotes-out-dXX`.
Шрифты: Prata, Cormorant Garamond, PT Serif (SIL Open Font License, `fonts/OFL.txt`).

## Автовыкладка на сервере
Установка (повторный запуск обновляет):
`curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/quotes/deploy_quotes.sh | bash`
Бот — `/root/quotes-bot`, команда `quotes` (status, login, check, now, pause, resume, log, update).
Cron каждые 10 минут; ролики выходят по порядку плана в 09:00, 14:00, 19:00 МСК, файл качается с GitHub перед выкладкой и удаляется после.
