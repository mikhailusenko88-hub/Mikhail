#!/usr/bin/env python3
"""Правки сайта из CRM («Редактор сайта») → каталог 0f7s1eez/index.html и 0f7s1eez/site-content.json → пересборка.

Запускает GitHub Actions «Сайт — правки из CRM» (ветка main, .github/workflows/site-edits.yml) раз в 10 минут:
    python3 nashdekor-build/apply_edits.py ПРАВКИ.json https://crm.nashdekor.ru
ПРАВКИ.json — ответ https://crm.nashdekor.ru/api/site/edits?after=<last_id> ({"edits": [...]}).

Виды правок (data — поля, photos — файлы, которые забираются с CRM /api/site/photo/<файл>):
  product      товар новый или изменённый: a, c, n, d, w, t, l, b, r (+ m — материал, mk — производитель для новых разделов);
               photos[0] — главное фото
  delete       убрать товар насовсем: a
  hide/unhide  скрыть товар с сайта на время / вернуть: a (скрытые хранятся в site-content.json → hidden)
  gallery_add  доп. фото товара: a, photos[]           gallery_del  убрать доп. фото: a, files[]
  kind         новый раздел или его тексты: code (пусто — новый), label, menu, h1, intro, title, description, faq, about,
               material, maker, avito (panel|mold|plinth|'' — куда класть на Авито)
  kind_del     удалить новый раздел (если в нём нет товаров): code
  section      тексты существующего раздела: code, menu, h1, intro, title, description, faq
  home         тексты главной: texts {ключ: текст} (ключи — метки <!--ed:ключ--> в index.html); photos[0] — главная картинка
  article      статья: slug (пусто — новая), builtin (старая статья — меняются только title, h1, description, lead, hidden),
               title, h1, description, lead, body, date, hidden, caps[] — подписи к photos[], drop_photos[]
  article_del  статья: slug, builtin (старая — скрывается, новая — удаляется)
  review       отзыв: id (пусто — новый), name, place, text, date, article; photos[], drop_photos[]     review_del  отзыв: id
  shop         контакты: max, telegram, avito
Итог каждой правки — в 0f7s1eez/site-edits.json (CRM показывает «на сайте» или «ошибка: причина»).
Если build.py падает — index.html и site-content.json возвращаются как были, все правки — «ошибка». Нужен Pillow.
"""
import copy, datetime, html, io, json, os, re, shutil, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "0f7s1eez")
INDEX = os.path.join(SITE, "index.html")
CONTENT = os.path.join(SITE, "site-content.json")
RESULT = os.path.join(SITE, "site-edits.json")
BUILTIN = {"panel", "color", "mold", "plinth", "cornice", "corner"}
ART_RE = re.compile(r"^[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 /.-]{0,19}$")
# правила текстов магазина (SEO-задание 09.11.2026): для товаров ARTDEC — строго; для новых разделов — без класса горючести, «рамок» и бренда
STRICT = [r"\bмдф\b", r"\bпвх\b", r"пенопласт", r"вспенен", r"\bг\s?[1-4]\b", r"горюч|пожарн", r"\bрам(к|ок)", r"алюмини", r"artdec|арт\s?дек"]
SOFT = [r"\bг\s?[1-4]\b", r"горюч|пожарн", r"\bрам(к|ок)", r"artdec|арт\s?дек"]
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
NOWS = NOW.strftime("%Y-%m-%d %H:%M")
TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f",
                                                   "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


class Bad(Exception):
    pass


def translit(s, sep="-"):
    t = "".join(TR.get(ch, ch) for ch in s.lower())
    return re.sub(r"[^a-z0-9]+", sep, t).strip(sep)


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
def slug(a): return a.lower().replace("/", "-").replace(" ", "")


def words(rules, *texts):
    low = " ".join(str(t or "") for t in texts).lower()
    if any(re.search(rx, low) for rx in rules): raise Bad("в тексте запрещённое слово (правила магазина)")


def need(d, f, lo, hi, name):
    v = str(d.get(f, "") or "").strip()
    if not lo <= len(v) <= hi: raise Bad("%s: от %d до %d знаков" % (name, lo, hi))
    return v


def faq_list(v):
    out = []
    for q in v or []:
        if isinstance(q, (list, tuple)) and len(q) == 2 and str(q[0]).strip() and str(q[1]).strip():
            out.append([str(q[0]).strip()[:200], str(q[1]).strip()[:1200]])
    return out[:15]


def check_product(d, kinds):
    a = str(d.get("a", "")).strip()
    if not ART_RE.match(a): raise Bad("неверный артикул")
    c = d.get("c")
    if c not in BUILTIN and c not in kinds: raise Bad("нет такого раздела")
    need(d, "n", 10, 160, "название"); need(d, "d", 5, 600, "описание")
    for f, lo, hi in (("w", 1, 3000), ("t", 1, 500), ("l", 50, 6000), ("b", 1, 1000), ("r", 1, 1000000)):
        if not isinstance(d.get(f), int) or not lo <= d[f] <= hi: raise Bad("поле %s вне пределов" % f)
    words(SOFT if c in kinds else STRICT, d.get("n"), d.get("d"), d.get("m"), d.get("mk"))
    item = {k: d[k] for k in ("a", "c", "n", "d", "w", "t", "l", "b", "r")}
    if c in kinds:
        for k in ("m", "mk"):
            v = str(d.get(k, "") or "").strip()[:120]
            if v: item[k] = v
    return item


class Photos:
    def __init__(self, crm):
        self.crm = crm

    def get(self, name):
        if not re.match(r"^[0-9]{1,9}(-[0-9]{1,3})?\.(jpg|png)$", name or ""): raise Bad("неверное имя фото")
        with urllib.request.urlopen("%s/api/site/photo/%s" % (self.crm, name), timeout=60) as r:
            return r.read(16 * 1024 * 1024)

    def save(self, name, out, sizes, min_w=600):
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(self.get(name)))).convert("RGB")
        if im.width < min_w: raise Bad("фото слишком маленькое (%d px в ширину, нужно от %d)" % (im.width, min_w))
        for sub, w in sizes:
            o = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            os.makedirs(os.path.join(SITE, sub), exist_ok=True)
            o.save(os.path.join(SITE, sub, out), "JPEG", quality=85, optimize=True, progressive=True)


def main():
    edits = json.load(open(sys.argv[1], encoding="utf-8")).get("edits", [])
    ph = Photos(sys.argv[2].rstrip("/"))
    src0 = open(INDEX, encoding="utf-8").read()
    try: content0 = open(CONTENT, encoding="utf-8").read()
    except OSError: content0 = None
    content = json.loads(content0) if content0 else {}
    for k, v in (("kinds", {}), ("sections", {}), ("gallery", {}), ("articles", []), ("article_over", {}), ("reviews", []), ("hidden", {})):
        content.setdefault(k, v)
    src = src0
    try: result = json.load(open(RESULT, encoding="utf-8"))
    except (OSError, ValueError): result = {}
    done = result.get("edits", {})
    last = int(result.get("last_id", 0))
    i0, i1 = find_value(src, "CAT"); cat = json.loads(src[i0:i1])
    p0, p1 = find_value(src, "PHOTO"); photo = json.loads(src[p0:p1])
    shop_new, home_new, hero = None, {}, None
    cat_slugs = set(os.listdir(os.path.join(SITE, "catalog"))) if os.path.isdir(os.path.join(SITE, "catalog")) else set()

    def find(a):
        return next((n for n, x in enumerate(cat) if key(x["a"]) == key(a)), None)

    for e in sorted(edits, key=lambda x: x["id"]):
        eid = int(e["id"])
        if eid <= last: continue
        last = max(last, eid)
        kind, d = e.get("kind"), e.get("data") or {}
        photos = e.get("photos") or ([e["photo"]] if e.get("photo") else [])
        snap = (copy.deepcopy(cat), copy.deepcopy(photo), copy.deepcopy(content), dict(home_new), hero, shop_new)
        kinds = content["kinds"]
        try:
            if kind == "product":
                item = check_product(d, kinds)
                pos = find(item["a"])
                if pos is not None:
                    old = cat[pos]
                    for k in ("m", "mk"): old.pop(k, None)
                    old.update(item); item = old; note = "изменён"
                elif key(item["a"]) in {key(k) for k in content["hidden"]}:
                    raise Bad("такой товар скрыт — сначала верните его на сайт")
                else:
                    if not photos: raise Bad("у нового товара нет фото")
                    after = max([n for n, x in enumerate(cat) if x.get("c") == item["c"]], default=len(cat) - 1)
                    cat.insert(after + 1, item); note = "добавлен"
                if photos:
                    name = "%s-e%d.jpg" % (photo_base(item["a"]), eid)   # новое имя — браузеры не покажут старое фото из кэша
                    ph.save(photos[0], name, (("img", 790), (os.path.join("img", "2x"), 1580)))
                    photo[item["a"]] = name; note += ", новое фото"
            elif kind == "delete":
                pos = find(str(d.get("a", e.get("article", ""))))
                if pos is None: raise Bad("такого товара на сайте уже нет")
                a = cat.pop(pos)["a"]
                photo.pop(a, None); content["gallery"].pop(a, None)
                gone = os.path.join(SITE, "p", slug(a))
                if os.path.isdir(gone): shutil.rmtree(gone)
                note = "убран с сайта"
            elif kind == "hide":
                pos = find(d.get("a", ""))
                if pos is None: raise Bad("такого товара на сайте нет")
                x = cat.pop(pos)
                content["hidden"][x["a"]] = {"item": x, "photo": photo.pop(x["a"], ""), "at": NOWS}
                note = "скрыт с сайта"
            elif kind == "unhide":
                hk = next((k for k in content["hidden"] if key(k) == key(d.get("a", ""))), None)
                if not hk: raise Bad("этот товар не скрыт")
                if find(hk) is not None: raise Bad("товар с таким артикулом уже на сайте")
                h = content["hidden"].pop(hk); x = h["item"]
                after = max([n for n, y in enumerate(cat) if y.get("c") == x.get("c")], default=len(cat) - 1)
                cat.insert(after + 1, x)
                if h.get("photo"): photo[x["a"]] = h["photo"]
                note = "снова на сайте"
            elif kind == "gallery_add":
                pos = find(d.get("a", ""))
                if pos is None: raise Bad("такого товара на сайте нет")
                a = cat[pos]["a"]; lst = content["gallery"].setdefault(a, [])
                if not photos: raise Bad("нет фото")
                if len(lst) + len(photos) > 12: raise Bad("у товара может быть до 12 доп. фото")
                for n, f in enumerate(photos, 1):
                    name = "%s-g%d-%d.jpg" % (photo_base(a), eid, n)
                    ph.save(f, name, (("img", 790), (os.path.join("img", "2x"), 1580)))
                    lst.append(name)
                note = "добавлено фото: %d" % len(photos)
            elif kind == "gallery_del":
                a = next((k for k in content["gallery"] if key(k) == key(d.get("a", ""))), None)
                files = set(d.get("files") or [])
                if not a or not files: raise Bad("нечего убирать")
                before = len(content["gallery"][a])
                content["gallery"][a] = [f for f in content["gallery"][a] if f not in files]
                n_del = before - len(content["gallery"][a])
                if not content["gallery"][a]: content["gallery"].pop(a)
                note = "убрано фото: %d" % n_del
            elif kind == "kind":
                code = str(d.get("code", "") or "")
                k = {"label": need(d, "label", 3, 60, "как называется один товар"), "menu": need(d, "menu", 3, 40, "название раздела"),
                     "h1": str(d.get("h1", "") or "").strip()[:120], "intro": need(d, "intro", 20, 1500, "вводный текст"),
                     "title": str(d.get("title", "") or "").strip()[:120], "description": str(d.get("description", "") or "").strip()[:250],
                     "faq": faq_list(d.get("faq")), "about": str(d.get("about", "") or "").strip()[:1500],
                     "material": str(d.get("material", "") or "").strip()[:120], "maker": str(d.get("maker", "") or "").strip()[:120],
                     "avito": d.get("avito") if d.get("avito") in ("panel", "mold", "plinth") else ""}
                words(SOFT, *[v for v in k.values() if isinstance(v, str)], *[x for q in k["faq"] for x in q])
                if code:
                    if code not in kinds: raise Bad("нет такого раздела")
                    k["slug"] = kinds[code]["slug"]; kinds[code] = k; note = "раздел обновлён"
                else:
                    base = translit(k["menu"], "_")[:20] or "razdel"
                    code = "k_" + base; n = 2
                    while code in kinds or code in BUILTIN: code = "k_%s%d" % (base, n); n += 1
                    sl = s0 = translit(k["menu"])[:40] or "razdel"; n = 2
                    while sl in cat_slugs or any(v.get("slug") == sl for v in kinds.values()): sl = "%s-%d" % (s0, n); n += 1
                    k["slug"] = sl; kinds[code] = k; note = "раздел создан: /catalog/%s/" % sl
            elif kind == "kind_del":
                code = str(d.get("code", ""))
                if code not in kinds: raise Bad("нет такого раздела")
                if any(x.get("c") == code for x in cat) or any(h["item"].get("c") == code for h in content["hidden"].values()):
                    raise Bad("в разделе есть товары — сначала уберите их или перенесите")
                gone = os.path.join(SITE, "catalog", kinds[code]["slug"])
                kinds.pop(code)
                if os.path.isdir(gone): shutil.rmtree(gone)
                note = "раздел удалён"
            elif kind == "section":
                code = str(d.get("code", ""))
                if code in kinds: raise Bad("это новый раздел — его тексты меняются в «Новые разделы»")
                o = {f: str(d.get(f, "") or "").strip()[:lim] for f, lim in (("menu", 40), ("h1", 120), ("intro", 1500), ("title", 120), ("description", 250))}
                o = {f: v for f, v in o.items() if v}
                fq = faq_list(d.get("faq"))
                if fq: o["faq"] = fq
                words(STRICT, *o.values(), *[x for q in fq for x in q])
                content["sections"][code] = o; note = "тексты раздела обновлены"
            elif kind == "home":
                texts = {k: str(v).strip() for k, v in (d.get("texts") or {}).items() if re.match(r"^[a-z0-9_]{2,30}$", k)}
                for k, v in texts.items():
                    if not 2 <= len(v) <= 1200: raise Bad("текст «%s»: от 2 до 1200 знаков" % k)
                    if "<!--ed:%s-->" % k not in src: raise Bad("на главной нет блока «%s»" % k)
                words(STRICT, *texts.values())
                home_new.update(texts)
                if photos:
                    name = "hero-e%d.jpg" % eid
                    ph.save(photos[0], name, (("img", 1006), (os.path.join("img", "2x"), 2012)), min_w=1000)
                    hero = name
                note = "главная обновлена"
            elif kind == "article":
                sl = str(d.get("slug", "") or "")
                f = {k: str(d.get(k, "") or "").strip() for k in ("title", "h1", "description", "lead")}
                if d.get("builtin"):
                    if not sl: raise Bad("нет статьи")
                    o = {k: v for k, v in f.items() if v}
                    o["hidden"] = bool(d.get("hidden"))
                    words(STRICT, *f.values())
                    content["article_over"][sl] = o; note = "статья скрыта" if o["hidden"] else "статья обновлена"
                else:
                    need(d, "title", 10, 120, "заголовок"); need(d, "description", 20, 250, "описание для поиска")
                    body = need(d, "body", 100, 30000, "текст статьи")
                    words(STRICT, *f.values(), body)
                    arts = content["articles"]
                    cur = next((x for x in arts if x["slug"] == sl), None) if sl else None
                    if sl and not cur: raise Bad("нет такой статьи")
                    pics = list(cur.get("photos", [])) if cur else []
                    caps = d.get("caps") or []
                    for n, fn in enumerate(photos, 1):
                        name = "%s-%d-%d.jpg" % ((sl or translit(f["title"])[:40] or "statya"), eid, n)
                        ph.save(fn, name, ((os.path.join("img", "stati"), 1200),))
                        pics.append({"f": name, "cap": str(caps[n - 1])[:150] if n - 1 < len(caps) else ""})
                    drop = set(d.get("drop_photos") or [])
                    pics = [p for p in pics if p["f"] not in drop]
                    rec = {"title": f["title"], "h1": f["h1"] or f["title"], "description": f["description"], "lead": f["lead"], "body": body,
                           "photos": pics, "hidden": bool(d.get("hidden")),
                           "date": (cur or {}).get("date") or (d.get("date") if re.match(r"^\d{4}-\d{2}-\d{2}$", str(d.get("date", ""))) else NOW.strftime("%Y-%m-%d"))}
                    if cur:
                        cur.update(rec); note = "статья обновлена"
                    else:
                        new_sl = s0 = translit(f["title"])[:60] or "statya"; n = 2
                        existing = set(os.listdir(os.path.join(SITE, "stati"))) if os.path.isdir(os.path.join(SITE, "stati")) else set()
                        try: existing |= {x["slug"] for x in json.load(open(os.path.join(SITE, "site-index.json"), encoding="utf-8")).get("articles", [])}
                        except (OSError, ValueError, KeyError, TypeError): pass
                        while new_sl in existing or any(x["slug"] == new_sl for x in arts): new_sl = "%s-%d" % (s0, n); n += 1
                        rec["slug"] = new_sl; arts.append(rec); note = "статья добавлена: /stati/%s/" % new_sl
            elif kind == "article_del":
                sl = str(d.get("slug", ""))
                if d.get("builtin"):
                    content["article_over"].setdefault(sl, {})["hidden"] = True; note = "статья скрыта"
                else:
                    before = len(content["articles"])
                    content["articles"] = [x for x in content["articles"] if x["slug"] != sl]
                    if len(content["articles"]) == before: raise Bad("нет такой статьи")
                    note = "статья удалена"
            elif kind == "review":
                rid = str(d.get("id", "") or "")
                r = {"name": need(d, "name", 2, 60, "имя"), "place": str(d.get("place", "") or "").strip()[:80],
                     "text": need(d, "text", 10, 2000, "текст отзыва"), "article": str(d.get("article", "") or "").strip()[:20],
                     "date": d.get("date") if re.match(r"^\d{4}-\d{2}-\d{2}$", str(d.get("date", ""))) else NOW.strftime("%Y-%m-%d")}
                cur = next((x for x in content["reviews"] if str(x.get("id")) == rid), None) if rid else None
                if rid and not cur: raise Bad("нет такого отзыва")
                pics = list(cur.get("photos", [])) if cur else []
                for n, fn in enumerate(photos, 1):
                    name = "r%d-%d.jpg" % (eid, n)
                    ph.save(fn, name, ((os.path.join("img", "otzyvy"), 1200),), min_w=400)
                    pics.append(name)
                drop = set(d.get("drop_photos") or [])
                r["photos"] = [p for p in pics if p not in drop][:8]
                if cur: cur.update(r); note = "отзыв обновлён"
                else: r["id"] = eid; content["reviews"].append(r); note = "отзыв добавлен"
            elif kind == "review_del":
                rid = str(d.get("id", ""))
                before = len(content["reviews"])
                content["reviews"] = [x for x in content["reviews"] if str(x.get("id")) != rid]
                if len(content["reviews"]) == before: raise Bad("нет такого отзыва")
                note = "отзыв удалён"
            elif kind == "shop":
                new = {k: str(d.get(k, "")) for k in ("max", "telegram", "avito")}
                for v in new.values():
                    if v and not re.match(r"^https://[^\s\"<>\\]{3,200}$", v): raise Bad("ссылка должна начинаться с https://")
                shop_new = new; note = "контакты обновлены"
            else:
                raise Bad("неизвестная правка")
            done[str(eid)] = {"ok": True, "note": note, "at": NOWS}
        except Exception as ex:  # одна плохая правка не мешает остальным: всё, что она успела поменять, откатываем
            cat, photo, content, home_new, hero, shop_new = snap
            done[str(eid)] = {"ok": False, "note": "ошибка: %s" % ex, "at": NOWS}
        print("правка №%d (%s %s): %s" % (eid, kind, e.get("article", ""), done[str(eid)]["note"]))

    # index.html: CAT (компактно, как было), PHOTO, SHOP, тексты главной, главная картинка
    new_src = src[:i0] + json.dumps(cat, ensure_ascii=False, separators=(",", ":")) + src[i1:]
    p0, p1 = find_value(new_src, "PHOTO")
    new_src = new_src[:p0] + json.dumps(photo, ensure_ascii=False) + new_src[p1:]
    if shop_new is not None:
        for k, v in shop_new.items():
            new_src = re.sub(r'(const SHOP = \{[^}]*?\b%s:\s*")[^"]*(")' % k, lambda m: m.group(1) + v + m.group(2), new_src, count=1)
    for k, v in home_new.items():
        new_src = re.sub(r"<!--ed:%s-->.*?<!--/ed:%s-->" % (k, k), lambda m: "<!--ed:%s-->%s<!--/ed:%s-->" % (k, html.escape(v, quote=False), k), new_src, flags=re.S)
    if hero:
        new_src = re.sub(r'(<div class="wall"><img src=")img/[^"]+(" srcset=")img/[^ "]+ 1006w, img/2x/[^ "]+ 2012w',
                         lambda m: '%simg/%s%simg/%s 1006w, img/2x/%s 2012w' % (m.group(1), hero, m.group(2), hero, hero), new_src, count=1)
    open(INDEX, "w", encoding="utf-8").write(new_src)
    with open(CONTENT, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=1)
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py")], cwd=os.path.dirname(HERE), capture_output=True, text=True)
    print(r.stdout[-2000:]); print(r.stderr[-3000:], file=sys.stderr)
    if r.returncode != 0:
        open(INDEX, "w", encoding="utf-8").write(src0)
        if content0 is None:
            os.remove(CONTENT)
        else:
            open(CONTENT, "w", encoding="utf-8").write(content0)
        subprocess.run([sys.executable, os.path.join(HERE, "build.py")], cwd=os.path.dirname(HERE), capture_output=True)
        why = (r.stderr.strip().splitlines() or ["сборка сайта не прошла"])[-1][:200]
        for e in edits:
            if done.get(str(e["id"]), {}).get("ok"):
                done[str(e["id"])] = {"ok": False, "note": "ошибка сборки сайта: %s" % why, "at": NOWS}
    keep = sorted(done, key=lambda k: int(k))[-300:]
    json.dump({"last_id": last, "updated": NOWS, "edits": {k: done[k] for k in keep}},
              open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("готово: правок %d, товаров на сайте %d" % (len(edits), len(cat)))


if __name__ == "__main__":
    main()
