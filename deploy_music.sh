#!/bin/bash
# Установка фоновой музыки в боты роликов («Почему так?» и «Білесің бе?»).
# Запуск на сервере:  curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/music/deploy_music.sh | bash
# Безопасно: перед изменениями делает копии config.json и make_video.py (*.bak-ДАТА),
# при ошибке проверки всё возвращает назад. Повторный запуск ничего не ломает.
set -u
RAW="${MUSIC_RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/music}"
STAMP=$(date +%Y%m%d-%H%M%S)

dl() {  # dl URL FILE
  if command -v curl >/dev/null; then curl -fsSL --retry 3 -o "$2" "$1"; else wget -q -O "$2" "$1"; fi
}

echo "== Ищу боты (папки с make_video.py и config.json)…"
mapfile -t DIRS < <(find "${SEARCH_ROOT:-/}" -xdev -name make_video.py -not -path '*/proc/*' -not -path '*/.git/*' \
                    -not -path '*/node_modules/*' -not -path '*/music_tmp/*' 2>/dev/null | xargs -r -n1 dirname | sort -u)
FOUND=0
for D in "${DIRS[@]}"; do
  [ -f "$D/config.json" ] || continue
  FOUND=1
  LANG_=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$D/config.json" 2>/dev/null || echo ru)
  if [ "$LANG_" = "kk" ]; then KIND=kz; else KIND=ru; fi
  echo
  echo "== Бот: $D  (канал: $([ $KIND = kz ] && echo 'Білесің бе?' || echo 'Почему так?'))"

  # 1) музыка
  mkdir -p "$D/music"
  if [ $KIND = kz ]; then
    FILES="kz/01_Dala_spokoyno.mp3 kz/02_Tulpar_energichno.mp3 kz/03_Kupiya_zagadka.mp3 kz/04_Toy_pozitiv.mp3"
  else
    FILES="ru/ru05_Zimnyaya_skazka.mp3"
  fi
  FILES="$FILES ru/skazka_02_LoFi.mp3 ru/skazka_05_Rep_bit.mp3 ru/lofi_01_Vecherniy_chay.mp3 ru/lofi_02_Dozhd.mp3 ru/bit_01_Staryy_dvor.mp3 ru/bit_02_Motor.mp3"
  OK=1
  for f in $FILES; do
    out="$D/music/$(basename "$f")"
    if dl "$RAW/$f" "$out.part" && [ -s "$out.part" ]; then mv -f "$out.part" "$out"; else rm -f "$out.part"; echo "   ! не скачался $f"; OK=0; fi
  done
  [ $OK = 1 ] && echo "   музыка: $(ls "$D/music"/*.mp3 | wc -l) трек(ов) в $D/music"

  # 2) config.json + make_video.py
  cp -p "$D/config.json" "$D/config.json.bak-$STAMP"
  cp -p "$D/make_video.py" "$D/make_video.py.bak-$STAMP"
  python3 - "$D" "$KIND" <<'PY'
import json, sys
from pathlib import Path
d, kind = Path(sys.argv[1]), sys.argv[2]
if kind == "kz":
    mp = {
        "Білесің бе?": ["03_Kupiya_zagadka.mp3", "01_Dala_spokoyno.mp3", "lofi_01_Vecherniy_chay.mp3", "skazka_02_LoFi.mp3"],
        "Аңыз ба, шындық па?": ["03_Kupiya_zagadka.mp3", "bit_01_Staryy_dvor.mp3", "skazka_05_Rep_bit.mp3"],
        "Қазақша сөз": ["04_Toy_pozitiv.mp3", "lofi_01_Vecherniy_chay.mp3"],
        "Топ-3": ["02_Tulpar_energichno.mp3", "bit_02_Motor.mp3", "skazka_05_Rep_bit.mp3"],
        "Мақал-мәтел": ["01_Dala_spokoyno.mp3", "lofi_02_Dozhd.mp3"],
        "Қай қала?": ["02_Tulpar_energichno.mp3", "04_Toy_pozitiv.mp3", "bit_02_Motor.mp3"],
    }
else:
    mp = {
        "Факт дня": ["ru05_Zimnyaya_skazka.mp3", "lofi_01_Vecherniy_chay.mp3", "skazka_02_LoFi.mp3"],
        "Миф или правда": ["bit_01_Staryy_dvor.mp3", "skazka_05_Rep_bit.mp3"],
        "Топ-3": ["bit_02_Motor.mp3", "skazka_05_Rep_bit.mp3"],
        "Как это работает": ["lofi_02_Dozhd.mp3", "skazka_02_LoFi.mp3"],
        "Загадка": ["ru05_Zimnyaya_skazka.mp3", "bit_01_Staryy_dvor.mp3"],
    }
cp = d / "config.json"
cfg = json.loads(cp.read_text(encoding="utf-8"))
cfg["music_volume"] = 0.15
cfg["music_by_format"] = mp
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

mv = d / "make_video.py"
src = mv.read_text(encoding="utf-8")
old = "        m = rnd.choice(music_files)\n"
new = ("        # музыка по смыслу рубрики (config.json -> music_by_format), иначе любая\n"
       "        want = (cfg.get(\"music_by_format\") or {}).get(script.get(\"format\") or \"\", [])\n"
       "        fit = [f for f in music_files if f.name in want]\n"
       "        m = rnd.choice(fit or music_files)\n")
if "music_by_format" in src:
    print("   код: выбор музыки по рубрике уже есть")
elif src.count(old) == 1:
    mv.write_text(src.replace(old, new), encoding="utf-8")
    print("   код: добавлен выбор музыки по рубрике")
elif "music_files" in src:
    print("   ! код: не нашёл строку выбора трека — музыка будет случайной из папки music/")
else:
    print("   ! код: в этой версии бота нет подмешивания музыки — нужна доработка")
print("   config: music_volume=0.15, рубрик с музыкой:", len(mp))
PY
  RC=$?
  if [ $RC -ne 0 ] || ! python3 -m py_compile "$D/make_video.py" || ! python3 -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$D/config.json"; then
    echo "   ! ошибка — возвращаю копии назад"
    cp -p "$D/config.json.bak-$STAMP" "$D/config.json"
    cp -p "$D/make_video.py.bak-$STAMP" "$D/make_video.py"
  else
    echo "   готово (копии: *.bak-$STAMP)"
  fi
  # если папка — git-клон, отметить, что файлы изменены локально
  if [ -d "$D/.git" ]; then echo "   (это git-клон, ветка: $(git -C "$D" rev-parse --abbrev-ref HEAD 2>/dev/null))"; fi
done
[ $FOUND = 1 ] || echo "!! Не нашёл ни одного бота (make_video.py + config.json)."
echo
echo "== Готово. Музыка появится в следующих роликах."
