"""Режим «Қай қала жеңеді?» для бота «Білесің бе?» — гонка 20 городов, 2 раза в день.

Включается в config.json: "mode": "race". Вернуть старые ролики-факты: "mode": "facts".
Турнир хранится в state.json → "race": номер заезда, очки городов, результаты.
"""
import datetime as dt
import json
import time


def run(BASE, cfg, log, notify, test=False, no_youtube=False):
    import race_video as rv
    state_f = BASE / "state.json"
    state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else \
        {"used_titles": [], "n_done": 0, "history": []}
    rs = state.setdefault("race", {"no": 0, "points": {}, "results": []})
    no = rs["no"] + 1
    out_dir = BASE / "out"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{dt.datetime.now():%Y-%m-%d_%H%M%S}_race{no}.mp4"
    info = rv.build_race(out, race_no=no, points=rs.get("points", {}), log=log, music_dir=BASE / "music",
                         handle=cfg.get("channel_handle", "@bilesin_be_kz"))
    out.with_suffix(".txt").write_text(info["title"] + "\n\n" + info["description"], encoding="utf-8")
    log(f"Заезд №{no}: победил {info['winner']}, топ-3: {', '.join(info['ranking'][:3])}")
    if test:
        log("Тестовый режим: ничего не выкладываю, турнир не меняю")
        return 0

    link = None
    want_yt = cfg.get("post_to_youtube") and (BASE / "yt_token.json").exists() and not no_youtube
    if want_yt:
        try:
            import yt_upload
            link = yt_upload.upload(out, info["title"], info["description"], info["tags"], cfg)
            log(f"YouTube: {link}")
        except Exception as e:
            log(f"YouTube: ошибка {e}")
            notify(f"Заезд №{no} собран, но не выложен: {e}")

    if link or not want_yt:   # заезд засчитываем, только если ролик вышел (или выкладка выключена)
        rs["no"] = no
        rs["points"] = info["points"]
        rs.setdefault("results", []).append({"no": no, "date": f"{dt.date.today()}", "winner": info["winner"],
                                             "top3": info["ranking"][:3], "link": link})
        rs["results"] = rs["results"][-300:]
        state["n_done"] = state.get("n_done", 0) + 1
        state.setdefault("history", []).append({"date": f"{dt.date.today()}", "title": info["title"],
                                                "links": [link] if link else ["вручную"]})
        state["history"] = state["history"][-200:]
        state_f.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    if want_yt:
        try:
            import yt_queue
            if yt_queue.pending():
                yt_queue.upload_next(cfg, 1)
        except Exception as e:
            log(f"Очередь YouTube: ошибка {e}")

    keep = cfg.get("keep_days", 7)
    for f in list(out_dir.glob("*.mp4")) + list(out_dir.glob("*.txt")):
        if time.time() - f.stat().st_mtime > keep * 86400:
            f.unlink()
    return 0 if (link or not want_yt) else 1
