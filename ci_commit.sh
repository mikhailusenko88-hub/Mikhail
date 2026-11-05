#!/bin/bash
# Сохранить таблицу, отчёт и контур карты обратно в ветку uz-race (ролики не храним, кроме тестовых).
git config user.name "uz-race-bot"
git config user.email "uz-race-bot@users.noreply.github.com"
for f in state.json status login uz_outline.json; do [ -e "$f" ] && git add -A "$f"; done
git diff --cached --quiet && exit 0
git commit -qm "$(head -1 status/last.txt 2>/dev/null | cut -c1-120)"
for i in 1 2 3 4 5; do
  git pull -q --rebase origin uz-race && git push -q origin HEAD:uz-race && exit 0
  sleep 7
done
exit 1
