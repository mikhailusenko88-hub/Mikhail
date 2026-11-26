"""Проверка перед коммитом: нет ли закрытого в том, что уходит в ОТКРЫТЫЙ репозиторий.
Правило Михаила (26.11.2026): каждый чат проверяет и убирает за собой. Подробно — CLAUDE.md в корне ветки main.

  python3 check_private.py --staged -m "текст сообщения"   — перед commit: добавленные строки + сообщение
  python3 check_private.py --history [N]                   — последние N коммитов ветки (по умолчанию 50)
  python3 check_private.py файл …                          — проверить файлы целиком
Код выхода 1 — что-то нашлось: переписать словами или открытыми цифрами и проверить снова.
Взять скрипт в любой клон: git fetch --depth=1 origin main && git show origin/main:.claude/check_private.py > /tmp/check_private.py
"""
import re
import subprocess
import sys

# Закрытые метрики кабинетов (YouTube Studio, Playgama/CrazyGames, Авито, Вебмастер, счётчик сайта)
METRIC = (r"(досматр|досмотр|просмотрено|пролистан|остались смотреть|ещё смотрят|удержан|retention|CTR|показ|impression"
          r"|ср\.\s?%|средн\w* (процент|%|время|длительн)|(?<![A-Za-z0-9])AVD(?![A-Za-z0-9])|аудитори|мужчин|женщин|(?<![А-Яа-яЁё])ТВ(?![А-Яа-яЁё])"
          r"|телевизор|Бразили|Инди|Казахстан|Росси|Украин|Узбекистан|Киргизи|Швеци|(?<![A-Za-z])США|eCPM|RPM|fill.?rate"
          r"|доход|выручк|конверси|отказ)")
NUM_PCT = r"\d+(?:[,.]\d+)?\s?%"
PATTERNS = [
    ("метрика %", re.compile(METRIC + r"[^.;\n]{0,40}?" + NUM_PCT, re.I)),
    ("% метрика", re.compile(NUM_PCT + r"[^.;\n]{0,25}?" + METRIC, re.I)),
    ("показы N", re.compile(r"\d[\d\s]*(?:[,.]\d+)?\s?(?:тыс\.\s)?показ\w*", re.I)),
    ("показы N", re.compile(r"показ\w*\s(?:за\s\S+\s)?—?\s?\d", re.I)),
    ("удержание", re.compile(r"0:(?:03|07|10|15|20|30|45)\s?[—-]\s?\d+\s?%")),
    ("секрет", re.compile(r"(ghp_[A-Za-z0-9]{20,}|github_pat_\w{20,}|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}"
                          r"|-----BEGIN [A-Z ]*PRIVATE KEY|(?:vless|vmess|ss|vpn|trojan)://\S{10,}"
                          r"|(?:password|passwd|пароль|token|secret)\w*\s*[:=]\s*[\"']?[A-Za-z0-9_\-.+/]{10,}[\"']?(?=\s|,|$))", re.I)),
]
ALLOW = re.compile(r"(цел[ьи]|→|\d+\s?%\+)", re.I)   # цели гипотез: «цель 45%+», «→ CTR выше 3%»


def scan_text(text, where):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, p in PATTERNS:
            for m in p.finditer(line):
                if kind != "секрет" and ALLOW.search(line[max(0, m.start() - 25):m.end() + 2]):
                    continue
                out.append(f"{where}:{i}: [{kind}] …{line[max(0, m.start() - 40):m.end() + 20].strip()}…")
    return out


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, errors="replace").stdout


SKIP = re.compile(r"(\.csv$|^history/|^status/)")   # снимки публичных страниц ботами (названия чужих роликов и т. п.)


def added_lines(diff):
    out, skip = [], False
    for l in diff.splitlines():
        if l.startswith("+++ "):
            skip = bool(SKIP.search(l[6:] if l.startswith("+++ b/") else l[4:]))
        elif l.startswith("+") and not skip:
            out.append(l[1:])
    return "\n".join(out)


def main():
    a = sys.argv[1:]
    found = []
    if "-m" in a:
        found += scan_text(a[a.index("-m") + 1], "сообщение")
    if "--staged" in a:
        found += scan_text(added_lines(git("diff", "--cached", "-U0")), "добавлено")
    if "--history" in a:
        i = a.index("--history")
        n = a[i + 1] if i + 1 < len(a) and a[i + 1].isdigit() else "50"
        for h in git("rev-list", f"--max-count={n}", "HEAD").split():
            found += scan_text(git("show", "-s", "--format=%B", h), f"{h[:7]} сообщение")
            found += scan_text(added_lines(git("show", "--format=", "-U0", h)), f"{h[:7]}")
    files = [x for j, x in enumerate(a) if not x.startswith("-") and (j == 0 or a[j - 1] not in ("-m", "--history"))]
    for f in files:
        try:
            found += scan_text(open(f, encoding="utf-8", errors="replace").read(), f)
        except (IsADirectoryError, FileNotFoundError):
            pass
    for s in found:
        print(s)
    if found:
        print(f"\nНайдено {len(found)}: похоже на закрытые данные. Переписать словами или открытыми цифрами и проверить снова. "
              "Если уже в GitHub — убрать самому (CLAUDE.md, «Каждый за собой»).")
        sys.exit(1)
    print("ок: закрытого не видно")


if __name__ == "__main__":
    main()
