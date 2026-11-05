#!/bin/bash
# Сохранить сезон и отчёт обратно в ветку flagball (ролики не храним).
git config user.name "flagball-bot"
git config user.email "flagball-bot@users.noreply.github.com"
for f in season_state.json races status; do [ -e "$f" ] && git add -A "$f"; done
git diff --cached --quiet && exit 0
git commit -qm "$(head -1 status/last.txt | cut -c1-120)"
for i in 1 2 3 4 5; do
  git pull -q --rebase origin flagball && git push -q origin HEAD:flagball && exit 0
  sleep 7
done
exit 1
