#!/usr/bin/env python3
"""Проверка запасного пути: если Альбина недоступна или сбилась посреди ролика — ролик выходит прежним голосом."""
import sys
from pathlib import Path

bot, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(bot))
import albina            # noqa: E402
import make_video as mv  # noqa: E402

sc = {"format": "Факт дня", "title": "Проверка запасного голоса",
      "lines": ["Это проверка запасного голоса.", "Вторая фраза.", "Третья фраза ролика."]}
cfg = {"voices": ["albina"], "channel_handle": "@pochemu_tak_fakty", "use_stock_video": False}
logs = []
res = []

# 1) Альбины нет совсем
albina.TTS_DIR = Path("/nonexistent")
albina.SERVICE = "http://127.0.0.1:9"
albina._st.update(off=False, mode=None, said=False)
mv.build(sc, cfg, out / "fallback_none.mp4", bot / "work", log=logs.append)
ok1 = any("прежним голосом" in l for l in logs)
res.append(f"нет Альбины → прежний голос: {'да' if ok1 else 'НЕТ'}")

# 2) Альбина сбилась на третьей фразе
albina.TTS_DIR = Path("/opt/multik-tts")
albina.SERVICE = "http://127.0.0.1:9"
albina._st.update(off=False, mode=None, said=False)
real = albina._synth
cnt = {"n": 0}


def flaky(*a, **k):
    cnt["n"] += 1
    if cnt["n"] >= 3:
        raise albina.AlbinaFailed("искусственный сбой")
    return real(*a, **k)


albina._synth = flaky
logs.clear()
mv.build(sc, cfg, out / "fallback_mid.mp4", bot / "work", log=logs.append)
ok2 = any("посреди ролика" in l for l in logs) and (out / "fallback_mid.mp4").stat().st_size > 50000
res.append(f"сбой посреди ролика → весь ролик прежним голосом: {'да' if ok2 else 'НЕТ'}")
res.append("лог: " + " | ".join(logs[-6:]))
(out / "fallback.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
print("\n".join(res))
sys.exit(0 if ok1 and ok2 else 1)
