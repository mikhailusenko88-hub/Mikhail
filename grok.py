# Барсик → Grok Imagine (xAI API): оживить готовый кадр из Blender.
# Запускается GitHub Actions (grok.yml) при изменении grok.txt.
# Ключ берётся из секрета репозитория XAI_API_KEY (console.x.ai → API Keys).
import base64, json, os, sys, time, urllib.request, urllib.error

API = "https://api.x.ai/v1"
OUT = "out/grok"
os.makedirs(OUT, exist_ok=True)
LOG = open(f"{OUT}/log.txt", "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n")
    LOG.flush()


def call(method, url, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "barsik-bot/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, {"raw": txt[:2000]}


def read_cfg(path="grok.txt"):
    cfg, shots = {}, []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, img, prompt = [p.strip() for p in line.split("|", 2)]
            shots.append((name, img, prompt))
        elif "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg, shots


def data_uri(path):
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def short(d):
    s = json.dumps(d, ensure_ascii=False)
    return s if len(s) < 1500 else s[:1500] + "…"


def make_shot(key, cfg, name, img, prompt):
    dur = int(cfg.get("duration", "6"))
    tries = [(cfg.get("model", "grok-imagine-video-1.5"), cfg.get("resolution", "1080p"))]
    for alt in [("grok-imagine-video-1.5", "720p"), ("grok-imagine-video", "720p")]:
        if alt not in tries:
            tries.append(alt)
    for model, res in tries:
        body = {"model": model, "prompt": prompt, "image": {"url": data_uri(img)},
                "duration": dur, "resolution": res}
        log(f"\n=== {name}: {model} {res} {dur}s ===")
        code, r = call("POST", f"{API}/videos/generations", key, body)
        log("POST", code, short(r))
        rid = r.get("request_id") or r.get("id")
        if code >= 300 or not rid:
            if code in (401, 402, 403):
                return None  # ключ/оплата — менять модель бесполезно
            continue
        t0 = time.time()
        while time.time() - t0 < 1200:
            time.sleep(6)
            code, s = call("GET", f"{API}/videos/{rid}", key)
            st = (s.get("status") or "").lower()
            if st not in ("processing", "pending", "queued", "in_progress", ""):
                log("GET", code, short(s))
            if st in ("done", "completed", "succeeded") or (s.get("video") or {}).get("url"):
                url = (s.get("video") or {}).get("url") or s.get("url")
                dst = f"{OUT}/{name}_{res}.mp4"
                req = urllib.request.Request(url, headers={"User-Agent": "barsik-bot/1.0"})
                with urllib.request.urlopen(req, timeout=300) as v, open(dst, "wb") as f:
                    f.write(v.read())
                log(f"ГОТОВО {dst} ({os.path.getsize(dst)//1024} КБ), {round(time.time()-t0)} с")
                return dst
            if st in ("failed", "error", "expired", "cancelled") or code >= 400:
                log("НЕ ВЫШЛО", code, short(s))
                break
        else:
            log("Не дождались 20 минут")
    return None


def main():
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        log("НЕТ КЛЮЧА: в репозитории нет секрета XAI_API_KEY.\n"
            "console.x.ai → API Keys → Create; затем GitHub → Settings → Secrets and variables → "
            "Actions → New repository secret, имя XAI_API_KEY.")
        return
    cfg, shots = read_cfg()
    log("Настройки:", cfg, "| кадров:", len(shots))
    done = [make_shot(key, cfg, *s) for s in shots]
    log("\nИТОГ:", [d for d in done if d])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log("ОШИБКА", repr(e))
        LOG.write(traceback.format_exc())
        sys.exit(1)
