# Flagball Arena — автовыкладка гонок 32 стран

GitHub Actions 3 раза в день (≈07:00, 15:00, 23:00 МСК) собирает новую гонку и выкладывает на YouTube-канал
Flagball Arena (@FlagballArenaTV): ролик, обложка, плейлист Daily Races. Лига (очередь стран, таблица месяца,
чемпионы) хранится здесь же в `league_state.json` и обновляется после каждой удачной выкладки.

- `.github/workflows/flagball.yml` — расписание (копия этого файла лежит в `main`, расписание работает только оттуда)
- `ci_run.py` — один запуск: гонка → обложка → YouTube → лига; отчёт в `status/last.txt`, список роликов `status/uploads.md`
- `yt.py` — загрузка через YouTube API; ключ — секрет репозитория `FLAGBALL_YT` (в ветке ключей нет)
- `fb-login.sh` — разовый вход в канал на сервере (ключ Google от бота «Білесің бе?»)
- `request.txt` — ручной запуск: поменять первую строку и запушить (`mode: test` — без выкладки)
- генератор: `race.py`, `track.py`, `phys.c`, `render.py`, `audio.py`, `league.py`, `thumb.py`, `fastvid.py`
- `flags/` — флаги (flag-icons, MIT), `fonts/` — Poppins (SIL OFL)
