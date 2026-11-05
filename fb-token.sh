#!/bin/bash
# Flagball Arena: показать вход для GitHub короткими строками — так он не портится при копировании с телефона.
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/flagball/fb-token.sh | bash
python3 - <<'PY'
import base64, hashlib, json, pathlib, sys
p = pathlib.Path("/root/flagball-login/token.json")
if not p.exists():
    sys.exit("Входа ещё нет. Сначала: curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/flagball/fb-login.sh | bash")
raw = json.dumps(json.loads(p.read_text()), separators=(",", ":")).encode()
s = "FB1:" + base64.b64encode(raw).decode() + ":" + hashlib.sha256(raw).hexdigest()[:8] + ":END"
print("Скопируй ВЕСЬ этот ответ целиком и вставь в GitHub (поле Secret у FLAGBALL_YT).\n")
for i in range(0, len(s), 24):
    print(s[i:i + 24])
PY
