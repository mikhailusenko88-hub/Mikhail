"""Проверка перед коммитом: нет ли в открытых файлах ветки закрытых цифр YouTube Studio.

  python3 tools/check_private.py            — проверить journal/*.md и README.md (код выхода 1, если нашлось)
  python3 tools/check_private.py файл …     — проверить свои файлы

Репозиторий открытый. Цифры Studio (досмотры, «просмотрено/пролистано», удержание на 0:10/0:30, CTR, показы,
средний % и время просмотра, страны и устройства в процентах, пол и возраст аудитории) — только в документы
проекта «Ютуб». Сюда — вывод словами («досматривают хуже, чем коробку 1») и открытые цифры (просмотры из RSS,
подписчики, лайки). Цели гипотез можно («цель 45%+», «→ CTR выше 3%»).
Случай 26.11.2026: в журнал попали показы серии 32 из Studio — пришлось переписывать историю ветки."""
import glob
import re
import sys

METRIC = r"(досматр|досмотр|просмотрено|пролистан|остались смотреть|ещё смотрят|удержан|CTR|показ|ср\.\s?%|средн\w* (процент|%|время|длительн)|AVD|аудитори|мужчин|женщин|(?<![А-Яа-яЁё])ТВ(?![А-Яа-яЁё])|телевизор|Бразили|Инди|Казахстан|Росси|Украин|Узбекистан|Киргизи|Швеци|(?<![A-Za-z])США)"
NUM_PCT = r"\d+(?:[,.]\d+)?\s?%"
PATTERNS = [
    re.compile(METRIC + r"[^.;\n]{0,40}?" + NUM_PCT, re.I),
    re.compile(NUM_PCT + r"[^.;\n]{0,25}?" + METRIC, re.I),
    re.compile(r"\d[\d\s]*(?:[,.]\d+)?\s?(?:тыс\.\s)?показ\w*", re.I),
    re.compile(r"показ\w*\s(?:за\s\S+\s)?—?\s?\d", re.I),
    re.compile(r"0:(?:03|07|10|15|20|30|45)\s?[—-]\s?\d+\s?%"),
]
ALLOW = re.compile(r"(цел[ьи]|→|\d+\s?%\+)", re.I)


def check(path):
    bad = []
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        for p in PATTERNS:
            for m in p.finditer(line):
                ctx = line[max(0, m.start() - 25):m.end() + 2]
                if ALLOW.search(ctx):
                    continue
                bad.append((i, line[max(0, m.start() - 40):m.end() + 20].strip()))
    return bad


def main():
    files = sys.argv[1:] or sorted(glob.glob("journal/*.md")) + ["README.md"]
    total = 0
    for f in files:
        for i, s in check(f):
            total += 1
            print(f"{f}:{i}: …{s}…")
    if total:
        print(f"\nНайдено {total}: похоже на закрытые цифры Studio. Заменить выводом словами или открытыми цифрами, "
              "потом коммитить. Если это открытые данные (просмотры из RSS, цель гипотезы) — переписать так, чтобы проверка не ловила.")
        sys.exit(1)
    print("ок: закрытых цифр Studio не видно")


if __name__ == "__main__":
    main()
