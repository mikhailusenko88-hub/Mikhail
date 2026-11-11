#!/usr/bin/env python3
"""Правки сайта из CRM («Редактор сайта») → каталог 0f7s1eez/index.html → пересборка страниц.

Запускает GitHub Actions «Сайт — правки из CRM» (ветка main, .github/workflows/site-edits.yml) раз в 10 минут:
    python3 nashdekor-build/apply_edits.py ПРАВКИ.json https://crm.nashdekor.ru
ПРАВКИ.json — ответ https://crm.nashdekor.ru/api/site/edits?after=<last_id> ({"edits": [...]}).
Виды правок: product (новый или изменённый товар, может быть с фото), delete (убрать товар), shop (контакты).
Итог каждой правки пишется в 0f7s1eez/site-edits.json — сервер забирает его вместе с сайтом, CRM показывает
«на сайте» или «ошибка: причина». Если build.py падает — каталог возвращается как был, все правки — «ошибка».
Нужен Pillow (уменьшение фото).
"""
import datetime, io, json, os, re, shutil, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "0f7s1eez")
INDEX = os.path.join(SITE, "index.html")
RESULT = os.path.join(SITE, "site-edits.json")
KINDS = {"panel", "color", "mold", "plinth", "cornice", "corner"}
ART_RE = re.compile(r"^[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 /.-]{0,19}$")
FORBIDDEN = [r"\bмдф\b", r"\bпвх\b", r"пенопласт", r"вспенен", r"\bг\s?[1-4]\b", r"горюч", r"\bрамк", r"алюмини", r"artdec|арт\s?дек"]
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d %H:%M")


def find_value(src, name):
    """(начало, конец) JSON-значения после «const NAME =» (с учётом строк в кавычках)."""
    m = re.search(r"\bconst %s\s*=\s*" % re.escape(name), src)
    i = m.end(); depth, in_str, esc = 0, False, False
    for j in range(i, len(src)):
        ch = src[j]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch in "[{": depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0: return i, j + 1
    raise ValueError(name)


def key(a): return str(a).upper().replace(" ", "")
def photo_base(a): return re.sub(r"[^A-Za-z0-9-]", "", a.replace("/", "-").replace(" ", "")) or "item"


def check_product(d):
    err = []
    a = str(d.get("a", "")).strip()
    if not ART_RE.match(a): err.append("неверный артикул")
    if d.get("c") not in KINDS: err.append("неверный раздел")
    n, desc = str(d.get("n", "")), str(d.get("d", ""))
    if not 10 <= len(n) <= 160: err.append("название 10–160 знаков")
    if not 5 <= len(desc) <= 600: err.append("описание 5–600 знаков")
    for f, lo, hi in (("w", 1, 2000), ("t", 1, 500), ("l", 100, 6000), ("b", 1, 1000), ("r", 1, 1000000)):
        if not isinstance(d.get(f), int) or not lo <= d[f] <= hi: err.append("поле %s вне пределов" % f)
    low = (n + " " + desc).lower()
    if any(re.search(rx, low) for rx in FORBIDDEN): err.append("запрещённое слово в тексте")
    return err


def save_photo(data, name):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    if im.width < 600: raise ValueError("фото слишком маленькое (%d px в ширину, нужно от 600)" % im.width)
    for sub, w in (("img", 790), (os.path.join("img", "2x"), 1580)):
        out = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        os.makedirs(os.path.join(SITE, sub), exist_ok=True)
        out.save(os.path.join(SITE, sub, name), "JPEG", quality=85, optimize=True, progressive=True)


def main():
    edits = json.load(open(sys.argv[1], encoding="utf-8")).get("edits", [])
    crm = sys.argv[2].rstrip("/")
    src0 = open(INDEX, encoding="utf-8").read()
    src = src0
    try: result = json.load(open(RESULT, encoding="utf-8"))
    except (OSError, ValueError): result = {}
    done = result.get("edits", {})
    last = int(result.get("last_id", 0))
    i0, i1 = find_value(src, "CAT"); cat = json.loads(src[i0:i1])
    p0, p1 = find_value(src, "PHOTO"); photo = json.loads(src[p0:p1])
    shop_new = None
    touched = []
    for e in sorted(edits, key=lambda x: x["id"]):
        eid = int(e["id"])
        if eid <= last: continue
        last = max(last, eid)
        kind, d = e.get("kind"), e.get("data") or {}
        try:
            if kind == "product":
                err = check_product(d)
                if err: raise ValueError(", ".join(err))
                item = {k: d[k] for k in ("a", "c", "n", "d", "w", "t", "l", "b", "r")}
                pos = next((n for n, x in enumerate(cat) if key(x["a"]) == key(item["a"])), None)
                if pos is not None:
                    old = cat[pos]; old.update(item); item = old; note = "изменён"
                else:
                    if not e.get("photo"): raise ValueError("у нового товара нет фото")
                    after = max([n for n, x in enumerate(cat) if x.get("c") == item["c"]], default=len(cat) - 1)
                    cat.insert(after + 1, item); note = "добавлен"
                if e.get("photo"):
                    with urllib.request.urlopen("%s/api/site/photo/%s" % (crm, e["photo"]), timeout=60) as r:
                        data = r.read(16 * 1024 * 1024)
                    name = "%s-e%d.jpg" % (photo_base(item["a"]), eid)   # новое имя — браузеры не покажут старое фото из кэша
                    save_photo(data, name)
                    photo[item["a"]] = name
                    note += ", новое фото"
                touched.append(item["a"])
            elif kind == "delete":
                a = key(d.get("a", e.get("article", "")))
                before = len(cat)
                cat = [x for x in cat if key(x["a"]) != a]
                if len(cat) == before: raise ValueError("такого товара на сайте уже нет")
                for k in [k for k in photo if key(k) == a]: photo.pop(k)
                gone = os.path.join(SITE, "p", str(d.get("a", e.get("article", ""))).lower().replace("/", "-").replace(" ", ""))
                if os.path.isdir(gone): shutil.rmtree(gone)   # страницу товара build.py сам не удаляет
                note = "убран с сайта"
            elif kind == "shop":
                shop_new = {k: str(d.get(k, "")) for k in ("max", "telegram", "avito")}
                for v in shop_new.values():
                    if v and not re.match(r"^https://[^\s\"<>\\]{3,200}$", v): raise ValueError("ссылка должна начинаться с https://")
                note = "контакты обновлены"
            else:
                raise ValueError("неизвестная правка")
            done[str(eid)] = {"ok": True, "note": note, "at": NOW}
        except Exception as ex:  # одна плохая правка не мешает остальным
            done[str(eid)] = {"ok": False, "note": "ошибка: %s" % ex, "at": NOW}
        print("правка №%d (%s %s): %s" % (eid, kind, e.get("article", ""), done[str(eid)]["note"]))
    # собрать index.html: CAT (компактно, как было), PHOTO, SHOP
    new_src = src[:i0] + json.dumps(cat, ensure_ascii=False, separators=(",", ":")) + src[i1:]
    p0, p1 = find_value(new_src, "PHOTO")
    new_src = new_src[:p0] + json.dumps(photo, ensure_ascii=False) + new_src[p1:]
    if shop_new is not None:
        for k, v in shop_new.items():
            new_src = re.sub(r'(const SHOP = \{[^}]*?\b%s:\s*")[^"]*(")' % k, lambda m: m.group(1) + v + m.group(2), new_src, count=1)
    open(INDEX, "w", encoding="utf-8").write(new_src)
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py")], cwd=os.path.dirname(HERE), capture_output=True, text=True)
    print(r.stdout[-2000:]); print(r.stderr[-3000:], file=sys.stderr)
    if r.returncode != 0:
        open(INDEX, "w", encoding="utf-8").write(src0)
        subprocess.run([sys.executable, os.path.join(HERE, "build.py")], cwd=os.path.dirname(HERE), capture_output=True)
        why = (r.stderr.strip().splitlines() or ["сборка сайта не прошла"])[-1][:200]
        for e in edits:
            if done.get(str(e["id"]), {}).get("ok"):
                done[str(e["id"])] = {"ok": False, "note": "ошибка сборки сайта: %s" % why, "at": NOW}
    keep = sorted(done, key=lambda k: int(k))[-300:]
    json.dump({"last_id": last, "updated": NOW, "edits": {k: done[k] for k in keep}},
              open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("готово: правок %d, товаров на сайте %d" % (len(edits), len(cat)))


if __name__ == "__main__":
    main()
