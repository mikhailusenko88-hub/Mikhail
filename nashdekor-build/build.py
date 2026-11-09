#!/usr/bin/env python3
"""Сборка страниц товаров и разделов сайта «Наш декор» (nashdekor.ru).

Источник данных — главная страница 0f7s1eez/index.html (массивы CAT, PROF, PHOTO, PAINT, SHOP):
цены, размеры и фото ведём там в одном месте, а этот скрипт делает из них:
  0f7s1eez/p/<артикул>/index.html      — страница каждого артикула (фото, 3D, цвет, профиль, цена, заявка)
  0f7s1eez/catalog/<раздел>/index.html — страница раздела со всеми артикулами
  0f7s1eez/assets/p.css, p.js          — общие стили и скрипт страниц
  0f7s1eez/sitemap.xml                 — карта сайта со всеми страницами
Запуск: python3 nashdekor-build/build.py   (из корня репозитория, ветка mebel)
Цены и наличие на страницах при заходе обновляются из CRM (crm.nashdekor.ru/api/catalog), как на главной.
"""
import json, os, re, html, datetime, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "0f7s1eez")
BASE = "https://nashdekor.ru"
TODAY = datetime.date.today().isoformat()

src = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()

def js_array(name):
    i = src.index("const %s=" % name) + len("const %s=" % name)
    depth = 0
    for j in range(i, len(src)):
        ch = src[j]
        if ch in "[{": depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0: return json.loads(src[i:j + 1])
    raise ValueError(name)

def js_assign(name):
    m = re.search(r"const %s\s*=\s*" % name, src); i = m.end(); depth = 0
    for j in range(i, len(src)):
        ch = src[j]
        if ch in "[{": depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0: return json.loads(src[i:j + 1])

CAT = js_array("CAT"); PROF = js_array("PROF"); PHOTO = js_assign("PHOTO"); PAINT = js_assign("PAINT")
# сечения молдингов, плинтусов, карнизов и уголков — сняты из PDF-каталога ARTDEC (extract_profiles.py)
PROF2 = json.load(open(os.path.join(HERE, "profiles-mold.json"), encoding="utf-8"))
shop_m = re.search(r"const SHOP = \{(.*?)\};", src)
SHOP = dict(re.findall(r'(\w+):\s*"([^"]*)"', shop_m.group(1)))
MSG = ("MAX " + SHOP["max"]) if SHOP.get("max") else ("Telegram " + SHOP["telegram"])   # основной мессенджер — как на главной
m = re.search(r"<style>\n/\* Layout(.*?)</style>", src, re.S)
BASE_CSS = "/* Базовые стили — копия с главной страницы (собирает build.py) */\n/* Layout" + m.group(1)
m = re.search(r'<style>(:root\{color-scheme.*?)</style>', src, re.S)
RESET_CSS = m.group(1)

KIND = {"panel": "Реечная панель", "color": "Панель под дерево", "mold": "Молдинг", "plinth": "Плинтус", "cornice": "Карниз", "corner": "Уголок"}
CATS = [  # код, адрес, название в меню, H1, вводный текст
    ("panel", "reechnye-paneli", "Рейки под покраску", "Реечные панели под покраску",
     "Стеновые реечные панели ARTDEC из высокоплотного полистирола, длина 3 м — стена до потолка без горизонтальных стыков. "
     "Поверхность под покраску: цвет подбирается под интерьер, стыки шпаклюются и красятся вместе с панелью. "
     "Профили — от классических каннелюр до широких ламелей и глубоких пазов. Класс пожарной опасности Г2. Цены за штуку, продаём поштучно и коробками."),
    ("color", "paneli-pod-derevo", "Рейки под дерево", "Реечные панели под дерево",
     "Панели с готовым декором под дерево и бетон на чёрной основе — красить не нужно. "
     "Три серии по числу ламелей на панели шириной 120 мм: серия 2 — две широкие ламели, серия 3 — три, серия 5 — пять узких. Длина 3 м. "
     "В коробке — один декор и одна серия."),
    ("mold", "moldingi", "Молдинги", "Молдинги для стен",
     "Настенные молдинги под покраску для рамок и панно на стенах, стыков обоев и покраски, зонирования. "
     "Ширина от 15 до 96 мм, длина 2 м (A611/3 и A611/4 — 3 м). У A35/2 и A157/2 сзади канал под кабель."),
    ("plinth", "plintusy", "Плинтусы", "Плинтусы напольные",
     "Напольные плинтусы под покраску высотой от 70 до 150 мм, длина 2 м. Красятся в цвет стен или дверей. "
     "Модели A11-80, A11-100 и A12-100 — с пазом под LED-ленту."),
    ("cornice", "karnizy", "Карнизы", "Потолочные карнизы",
     "Потолочные плинтусы (карнизы) под покраску от компактного A38 20×20 мм до широкого A504 180 мм, длина 2 м. "
     "Под скрытую LED-подсветку подходит карниз A503."),
    ("corner", "ugolki", "Уголки", "Уголки декоративные",
     "Уголки для внешних углов 22×22 и 30×30 мм, длина 2 м, под покраску — закрывают торцы панелей на углу и защищают угол."),
]
CAT_BY = {c[0]: c for c in CATS}
WOOD_NAMES = {"2": "две широкие ламели", "3": "три ламели", "5": "пять узких ламелей"}

def slug(a): return a.lower().replace("/", "-").replace(" ", "")
def esc(s): return html.escape(str(s), quote=True)
def fmt(n): return "{:,}".format(int(round(n))).replace(",", " ")
def photo(a): return "img/" + PHOTO[a] if PHOTO.get(a) else ""
def series(x): return x["a"].split("-")[0] if x["c"] == "color" else None
def wood_parts(x):
    n = {"2": 2, "3": 3, "5": 5}.get(series(x), 3); base = max(2, x["t"] * 0.35); step = x["w"] / n; slat = step * (0.62 if n < 5 else 0.55)
    return {"n": n, "base": round(base, 2), "slats": [[round(i * step + (step - slat) / 2, 2), round(i * step + (step + slat) / 2, 2)] for i in range(n)]}

def dims(x): return "%d×%d×%d мм" % (x["w"], x["t"], x["l"])
def title(x):
    a, c = x["a"], x["c"]
    if c == "panel": t = "Реечная панель %s %s под покраску — купить в СПб" % (a, dims(x))
    elif c == "color": t = "Панель под дерево %s (%s) %s — купить в СПб" % (a, x["d"].split(",")[0], dims(x))
    elif c == "mold": t = "Молдинг %s %s под покраску — купить в СПб" % (a, dims(x))
    elif c == "plinth": t = "Плинтус напольный %s %s — купить в СПб" % (a, dims(x))
    elif c == "cornice": t = "Карниз потолочный %s %s — купить в СПб" % (a, dims(x))
    else: t = "Уголок декоративный %s %s — купить в СПб" % (a, dims(x))
    return t + " | Наш декор"
def description(x):
    price = "Цена %s ₽ за шт, %d шт в коробке." % (fmt(x["r"]), x["b"]) if x.get("r") else "%d шт в коробке." % x["b"]
    return "%s: %s. %s Со склада в Санкт-Петербурге или под заказ 3–4 недели, доставка по СПб и Ленобласти. %s" % (
        x["n"], x["d"], price, "3D-просмотр, профиль и расчёт стены." if x["c"] in ("panel", "color") else "3D-просмотр, чертёж профиля и заявка на сайте.")

# ---------- чертёж профиля (сечение), мм ----------
def prof_svg(x):
    W, T = x["w"], x["t"]
    pts = PROF.get(x["a"]); wood = wood_parts(x) if x["c"] == "color" else None; poly = PROF2.get(x["a"])
    if not pts and not wood and not poly: return ""
    if poly: T = poly["t"]   # у карнизов вылет взят с чертежа
    fs = max(W / 30.0, (T + 6) / 9.0); sw = fs / 14.0; padL, padR, padT, padB = W * 0.03, fs * 7.5, fs * 1.6, fs * 3.4   # шрифт ~14–20 px на экране при любом масштабе
    vb = "%.1f %.1f %.1f %.1f" % (-padL, -padT, W + padL + padR, T + padT + padB)
    body = ""
    if pts:
        d = "M0,%.2f " % T + " ".join("L%.2f,%.2f" % (px, T - py) for px, py in pts) + " L%.2f,%.2f Z" % (W, T)
        body = '<path class="body" d="%s" stroke-width="%.2f"/>' % (d, sw * 1.2)
    elif poly:
        ring = lambda r: "M" + " L".join("%.2f,%.2f" % (px, T - py) for px, py in r) + " Z"
        d = " ".join(ring(r) for r in [poly["outer"]] + poly["holes"])
        body = '<path class="body" fill-rule="evenodd" d="%s" stroke-width="%.2f"/>' % (d, sw * 1.2)
    else:
        body = '<rect class="base" x="0" y="%.2f" width="%d" height="%.2f" stroke-width="%.2f"/>' % (T - wood["base"], W, wood["base"], sw)
        body += "".join('<rect class="slat" x="%.2f" y="0" width="%.2f" height="%.2f" stroke-width="%.2f"/>' % (a0, a1 - a0, T - wood["base"], sw) for a0, a1 in wood["slats"])
    y1 = T + fs * 1.1; y2 = T + fs * 2.6; xr = W + fs * 1.3
    dim = ('<g class="dimline" stroke-width="%.2f"><path d="M0,%.2f V%.2f M%d,%.2f V%.2f M0,%.2f H%d"/>'
           '<path d="M%.2f,0 H%.2f M%.2f,%d H%.2f M%.2f,0 V%d"/></g>' % (sw, T + fs * 0.3, y1 + fs * 0.4, W, T + fs * 0.3, y1 + fs * 0.4, y1, W,
                                                                         W + fs * 0.3, xr + fs * 0.4, W + fs * 0.3, T, xr + fs * 0.4, xr, T))
    txt = ('<text class="dim" x="%.2f" y="%.2f" text-anchor="middle" font-size="%.2f">%d мм</text>'
           '<text class="dim" x="%.2f" y="%.2f" text-anchor="start" font-size="%.2f" dominant-baseline="middle">%s мм</text>' % (W / 2, y2, fs, W, xr + fs * 0.5, T / 2, fs * 0.9, ("%d" % T) if float(T).is_integer() else ("%.0f" % T)))
    return '<svg viewBox="%s" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Профиль %s: ширина %d мм, толщина %.0f мм">%s%s%s</svg>' % (vb, esc(x["a"]), W, T, body, dim, txt)

# ---------- общие куски страницы ----------
def head(t, desc, canon, og_img, extra_ld, root):
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>%s</title><meta name="description" content="%s">'
            '<link rel="canonical" href="%s"><link rel="icon" href="%sfavicon.ico" sizes="any"><link rel="apple-touch-icon" href="%sapple-touch-icon.png">'
            '<meta property="og:type" content="%s"><meta property="og:site_name" content="Наш декор"><meta property="og:locale" content="ru_RU"><meta property="og:title" content="%s">'
            '<meta property="og:description" content="%s"><meta property="og:url" content="%s"><meta property="og:image" content="%s"><meta name="twitter:card" content="summary_large_image">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">%s'
            '<style>%s</style><link rel="stylesheet" href="%sassets/p.css?v=%s"></head><body>' % (
                esc(t), esc(desc), canon, root, root, "product" if "/p/" in canon else "website", esc(t), esc(desc), canon, og_img, extra_ld, RESET_CSS, root, VER))

def header(root):
    return ('<header class="top"><div class="wrap bar"><a class="logo" href="%s"><b>Наш</b> декор</a>'
            '<nav class="links"><a href="%s#catalog">Каталог</a><a href="%s#calc">Расчёт стены</a><a href="%s#pro">Дизайнерам</a><a href="%s#terms">Доставка и оплата</a><a href="#order">Заявка</a></nav>'
            '<a class="btn sm" href="#order">Заказать</a></div></header>' % (root, root, root, root, root))

def footer(root):
    return ('<footer><div class="wrap"><span><b>Наш</b> декор · Санкт-Петербург</span><span>%s</span>'
            '<nav aria-label="Документы" style="flex-basis:100%%;display:flex;flex-wrap:wrap;gap:6px 18px"><a href="%soferta.html" style="color:inherit">Оферта</a>'
            '<a href="%sprivacy.html" style="color:inherit">Политика конфиденциальности</a><a href="%sconsent.html" style="color:inherit">Согласие на обработку данных</a></nav>'
            '</div></footer>' % (esc(SHOP["legal"]), root, root, root))

def sections_nav(cur_code, root):
    return '<nav class="sections" aria-label="Разделы каталога">' + "".join(
        '<a href="%scatalog/%s/"%s>%s</a>' % (root, s, ' aria-current="page"' if code == cur_code else "", esc(menu)) for code, s, menu, _, _ in CATS) + "</nav>"

def crumbs(items):
    return '<nav class="crumbs" aria-label="Вы здесь">' + "".join('<span>%s</span>' % ('<a href="%s">%s</a>' % (h, esc(t)) if h else esc(t)) for t, h in items) + "</nav>"

def crumbs_ld(items, url_of):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": t, "item": url_of(h)} for i, (t, h) in enumerate(items) if h]}

def lead_form(x=None):
    prod = ('<div class="prodline"><b>%s %s</b>Количество: <span id="oQty">1</span> шт · цвет и количество подставятся в заявку</div>' % (esc(KIND[x["c"]]), esc(x["a"]))) if x else ""
    return ('<section class="porder" id="order"><div class="wrap"><div class="form"><div><h2>Заявка</h2>'
            '<p class="note" style="font-size:15px;margin-top:8px">Ответим с ценой, наличием и сроком в рабочее время. Удобнее всего — позвонить %s или написать в %s.</p>%s</div>'
            '<form class="panel stack" id="leadForm" novalidate><div class="two">'
            '<label class="f">Имя<input type="text" id="lName" autocomplete="name" required></label>'
            '<label class="f">Телефон или мессенджер<input type="text" id="lContact" autocomplete="tel" placeholder="+7 … или @ник" required></label></div>'
            '<label class="f">Кто вы<select id="lWho"><option>Делаю ремонт у себя</option><option>Дизайнер</option><option>Ремонтная бригада</option><option>Компания, объект</option></select></label>'
            '<label class="f">Комментарий<textarea id="lMsg" rows="3" placeholder="Адрес, сроки, нужна ли доставка"></textarea></label>'
            '<label class="chk" style="align-items:flex-start"><input type="checkbox" id="lAgree" required style="margin-top:3px"> <span>Я даю <a href="%sconsent.html" style="color:var(--ink)">согласие на обработку персональных данных</a> и ознакомлен с <a href="%sprivacy.html" style="color:var(--ink)">Политикой обработки персональных данных</a></span></label>'
            '<input type="text" id="lHp" name="website" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">'
            '<div class="err" id="lErr" hidden></div><button class="btn" type="submit" id="lSend">Отправить заявку</button><div id="lDone" hidden></div></form></div></div></section>'
            % (esc(SHOP["phone"]), esc(MSG), prod, ROOT, ROOT))

def card(x, root):
    ph = photo(x["a"])
    img = ('<img src="%s%s" alt="%s %s" loading="lazy" width="790" height="449">' % (root, ph, esc(KIND[x["c"]]), esc(x["a"]))) if ph else ""
    price = ('<b class="num">%s ₽</b>' % fmt(x["r"])) if x.get("r") else "<b>По запросу</b>"
    return ('<a class="card" href="%sp/%s/" data-p="%s"><div class="sw">%s</div><div class="in"><div class="eyebrow">%s</div><div class="art">%s</div><div class="d">%s</div>'
            '<div class="price">%s<small>за шт · %d шт в коробке</small><small class="stock">Под заказ, 3–4 недели</small></div></div></a>'
            % (root, slug(x["a"]), esc(x["a"]), img, esc(KIND[x["c"]]), esc(x["a"]), esc(x["d"]), price, x["b"]))

# ---------- тексты «о товаре» ----------
def about(x):
    c, a = x["c"], x["a"]
    out = []
    if c == "panel":
        out.append("<p>%s — стеновая реечная панель ARTDEC из высокоплотного полистирола, %s. Длина 3 м закрывает стену высотой до 3 м без горизонтального стыка; при большей высоте панели стыкуются по длине.</p>" % (esc(a), esc(x["d"].split(",")[0])))
        out.append("<p>Панель поставляется белой, под покраску: красится в любой цвет вместе со стеной, стыки между панелями шпаклюются. Монтаж на клей (жидкие гвозди), в среднем один тюбик на 5 панелей.</p>")
        out.append("<p><b>Сколько нужно:</b> ширина стены ÷ %d мм = число панелей в ряд, плюс запас 10%% на подрезку. Точный расчёт с плинтусом и карнизом — в <a href=\"%s?panel=%s#calc\" style=\"color:var(--ink)\">3D-расчёте стены</a>.</p>" % (x["w"], ROOT, esc(a)))
    elif c == "color":
        s = series(x)
        out.append("<p>%s — реечная панель серии %s (%s) с готовым декором «%s» на чёрной основе. Красить не нужно: ламели уже с покрытием, основа между ними матовая чёрная. Размер %s.</p>" % (esc(a), s, WOOD_NAMES.get(s, "ламели"), esc(x["d"].split(",")[0]), dims(x)))
        out.append("<p>Все декоры серии %s одинаковы по размеру и цене — их можно сочетать на одной стене. В коробке %d шт одного декора. Монтаж на клей (жидкие гвозди).</p>" % (s, x["b"]))
        out.append("<p><b>Сколько нужно:</b> ширина стены ÷ %d мм = число панелей в ряд, плюс запас 10%% на подрезку. Точный расчёт — в <a href=\"%s?panel=%s#calc\" style=\"color:var(--ink)\">3D-расчёте стены</a>.</p>" % (x["w"], ROOT, esc(a)))
    elif c == "mold":
        extra = " Сзади — канал под кабель." if "каналом" in x["d"] else ""
        extra += " Универсальный профиль: подходит как молдинг, плинтус или наличник." if "универсальный" in x["d"] else ""
        out.append("<p>%s — настенный молдинг ARTDEC под покраску, %s.%s Из него собирают рамки и панно на стенах, закрывают стык обоев и покраски, делят стену на зоны.</p>" % (esc(a), dims(x), extra))
        out.append("<p>Молдинг поставляется белым и красится вместе со стеной или в контрастный цвет. Монтаж на клей (жидкие гвозди), углы запиливаются под 45°. Для рамки считайте периметр плюс запас на подрезку.</p>")
    elif c == "plinth":
        led = " Паз под LED-ленту — подсветка пола." if "LED" in x["d"] else ""
        out.append("<p>%s — напольный плинтус ARTDEC под покраску высотой %d мм, толщина %d мм, длина 2 м.%s Красится в цвет стен, дверей или в контраст.</p>" % (esc(a), x["w"], x["t"], led))
        out.append("<p>Монтаж на клей (жидкие гвозди), углы запиливаются под 45°. Сколько нужно: периметр комнаты без дверных проёмов ÷ 2 м, плюс запас 10%% на подрезку. В коробке %d шт.</p>" % x["b"])
    elif c == "cornice":
        led = " Подходит под скрытую LED-подсветку." if "LED" in x["d"] else ""
        out.append("<p>%s — потолочный карниз (потолочный плинтус) ARTDEC под покраску, %s.%s Закрывает стык стены и потолка, красится в цвет потолка или стен.</p>" % (esc(a), dims(x), led))
        out.append("<p>Монтаж на клей, углы запиливаются под 45°. Сколько нужно: периметр потолка ÷ 2 м, плюс запас 10%% на подрезку. В коробке %d шт.</p>" % x["b"])
    else:
        out.append("<p>%s — декоративный уголок ARTDEC под покраску для внешних углов, %s. Закрывает торцы реечных панелей и обоев на углу и защищает угол от сколов.</p>" % (esc(a), dims(x)))
        out.append("<p>Монтаж на клей (жидкие гвозди). Сколько нужно: высота угла ÷ 2 м на каждый внешний угол. В коробке %d шт.</p>" % x["b"])
    return "".join(out)

# ---------- страница товара ----------
def product_page(x):
    a, c = x["a"], x["c"]
    sl = slug(a); url = "%s/p/%s/" % (BASE, sl); catc = CAT_BY[c]
    ph = photo(a); og_img = (BASE + "/" + ph) if ph else BASE + "/og.jpg"
    is_wood = c == "color"; has3d = a in PROF or is_wood or a in PROF2; is_panel = c in ("panel", "color")
    crumb_items = [("Главная", ROOT), (catc[2], "%scatalog/%s/" % (ROOT, catc[1])), (a, "")]
    ld_prod = {"@context": "https://schema.org", "@type": "Product", "name": x["n"], "sku": a, "mpn": a, "brand": {"@type": "Brand", "name": "ARTDEC"},
               "description": x["d"], "category": KIND[c], "url": url,
               "additionalProperty": [{"@type": "PropertyValue", "name": "Ширина", "value": x["w"], "unitText": "мм"}, {"@type": "PropertyValue", "name": "Толщина", "value": x["t"], "unitText": "мм"},
                                      {"@type": "PropertyValue", "name": "Длина", "value": x["l"], "unitText": "мм"}, {"@type": "PropertyValue", "name": "В коробке", "value": x["b"], "unitText": "шт"}]}
    if ph: ld_prod["image"] = [og_img]
    if x.get("r"): ld_prod["offers"] = {"@type": "Offer", "url": url, "priceCurrency": "RUB", "price": x["r"], "availability": "https://schema.org/BackOrder",
                                        "itemCondition": "https://schema.org/NewCondition", "seller": {"@type": "Organization", "name": "Наш декор"}}
    ld = '<script type="application/ld+json">%s</script><script type="application/ld+json">%s</script>' % (
        json.dumps(ld_prod, ensure_ascii=False), json.dumps(crumbs_ld(crumb_items, lambda h: BASE + "/" + h.replace(ROOT, "", 1) if h != ROOT else BASE + "/"), ensure_ascii=False))

    # вид: вкладки и сцена
    tabs = ""
    if has3d:
        cnt = ('<span class="sp"></span><span class="ncount" role="group" aria-label="Сколько панелей рядом"><span class="note">Панелей рядом</span>'
               '<button type="button" id="nMinus" aria-label="Меньше">−</button><b id="nVal">1</b><button type="button" id="nPlus" aria-label="Больше">+</button></span>') if is_panel else ""
        second = ('<button type="button" data-v="wall" aria-pressed="false">3D · моя стена</button>' if is_panel else
                  '<button type="button" data-v="full" aria-pressed="false">3D · вся длина %s м</button>' % (("%d" % (x["l"] // 1000)) if x["l"] % 1000 == 0 else "%.1f" % (x["l"] / 1000)))
        tabs = ('<div class="vtabs" role="group" aria-label="Вид"><button type="button" data-v="frag" aria-pressed="true">3D · %s</button>%s%s%s</div>'
                % ("панель" if is_panel else "фрагмент", second, '<button type="button" data-v="photo" aria-pressed="false">Фото</button>' if ph else "", cnt))
    stage = '<div class="pview%s" id="pview">' % (" is3d" if has3d else " photoonly")
    if has3d: stage += '<canvas id="c3" aria-label="%s %s в 3D"></canvas><div class="nogl" id="nogl" hidden>3D не запускается в этом браузере — посмотрите фото.</div>' % (esc(KIND[c]), esc(a))
    if ph: stage += '<img id="photo" src="%s%s" alt="%s %s — %s" width="790" height="449"%s>' % (ROOT, ph, esc(KIND[c]), esc(a), esc(x["d"]), " hidden" if has3d else "")
    elif not has3d: stage += '<div class="nogl">Фото скоро. Размеры и цена — ниже.</div>'
    stage += '<div class="hint" id="hint"></div></div>'
    if is_panel:
        stage += ('<div class="wallbox" id="wallBox" hidden><div class="wf"><label class="f">Ширина стены, см<input type="number" id="wW" min="10" step="1" value="320" inputmode="numeric"></label>'
                  '<label class="f">Высота, см<input type="number" id="wH" min="10" step="1" value="270" inputmode="numeric"></label>'
                  '<label class="f">Окна и двери, м²<input type="number" id="wO" min="0" step="0.1" value="0" inputmode="decimal"></label></div>'
                  '<label class="chk"><input type="checkbox" id="wR" checked> Запас 10%% на подрезку</label>'
                  '<div class="wres"><div><div class="eyebrow">На эту стену</div><b class="num" id="wPcs">—</b><small class="note" id="wPack"></small></div>'
                  '<div style="text-align:right"><div class="eyebrow">Предварительно</div><b class="num" id="wSum">—</b><small class="note" id="wArea"></small></div></div>'
                  '<div class="wbtns"><button class="btn" type="button" id="wOrder">Заказать это количество</button>'
                  '<a class="btn ghost" id="wFull" href="%s?panel=%s#calc">Расчёт с плинтусом и карнизом</a></div></div>' % (ROOT, esc(a)))

    # цвет / декор
    if is_wood:
        sibs = [y for y in CAT if series(y) == series(x)]
        colors = '<div class="colors"><div class="eyebrow">Декоры серии %s</div><div class="decors">%s</div><div class="cname">Декор: <b>%s</b></div></div>' % (
            series(x), "".join('<a href="%sp/%s/"%s><i style="background-image:url(\'%simg/dot/%s\')"></i>%s · %s</a>' % (
                ROOT, slug(y["a"]), ' aria-current="page"' if y["a"] == a else "", ROOT, PHOTO.get(y["a"], ""), esc(y["a"]), esc(y["d"].split(",")[0])) for y in sibs), esc(x["d"].split(",")[0]))
    else:
        colors = '<div class="colors" id="colors"></div>'

    prof = prof_svg(x)
    if a in PROF2:
        pv = PROF2[a]
        if c == "cornice": ptxt = "Сечение карниза в масштабе: высота по стене %d мм, вылет от стены ≈ %.0f мм (потолок слева, стена снизу). Контур снят с каталога производителя." % (x["w"], pv["t"])
        elif c == "plinth": ptxt = "Сечение плинтуса в масштабе: высота %d мм, толщина %d мм (верх плинтуса слева, стена снизу). Контур снят с каталога производителя." % (x["w"], x["t"])
        elif c == "corner": ptxt = "Сечение уголка в масштабе: полки %d×%d мм. Контур снят с каталога производителя." % (x["w"], x["t"])
        else: ptxt = "Сечение в масштабе: ширина %d мм, толщина %d мм (стена снизу). Контур снят с каталога производителя." % (x["w"], x["t"])
    else:
        ptxt = "Вид с торца в масштабе: ширина %d мм, толщина %d мм. %s" % (x["w"], x["t"], "Рельеф снят с каталога производителя." if a in PROF else "Схема: чёрная основа и ламели с декором.")
    prof_html = ('<div class="prof"><h2>Профиль (сечение)</h2><p>%s</p>%s</div>' % (ptxt, prof)) if prof else ""

    specs = [("Артикул", a), ("Тип", KIND[c]), ("Ширина", "%d мм" % x["w"]), ("Толщина", "%d мм" % x["t"]), ("Длина", "%d мм" % x["l"]),
             ("В коробке", "%d шт" % x["b"]), ("Материал", "высокоплотный полистирол"), ("Пожарная опасность", "класс Г2"),
             ("Покрытие", "декор «%s», красить не нужно" % x["d"].split(",")[0] if is_wood else "белый грунт, под покраску"),
             ("Производитель", "ARTDEC (Казахстан)")]
    if "LED" in x["d"]: specs.append(("Подсветка", "паз под LED-ленту"))
    if "каналом" in x["d"]: specs.append(("Кабель-канал", "есть, сзади"))
    specs_html = '<div class="specs"><h2>Характеристики</h2><table>%s</table></div>' % "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(k), esc(v)) for k, v in specs)

    price_b = ('<b class="num" id="price">%s ₽</b>' % fmt(x["r"])) if x.get("r") else '<b id="price">По запросу</b>'
    calc_btn = ('<a class="btn ghost" id="toCalc" href="%s?panel=%s#calc">Рассчитать на стену в 3D</a>' % (ROOT, esc(a))) if c in ("panel", "color") else ""
    buy = ('<aside class="buy" aria-label="Цена и заказ"><div class="price">%s<small>за штуку · %d шт в коробке</small></div><div class="stock" id="stock">Под заказ, 3–4 недели</div>'
           '<div class="qty"><button type="button" id="qMinus" aria-label="Меньше">−</button><input type="number" id="qty" min="1" max="9999" value="1" inputmode="numeric" aria-label="Количество, шт">'
           '<button type="button" id="qPlus" aria-label="Больше">+</button><button type="button" class="btn sm ghost" id="qBox">Коробка</button></div>'
           '<div class="total"><div><small>Итого, предварительно</small><b class="num" id="tSum">—</b></div><small id="tPack"></small></div>'
           '<button class="btn" type="button" id="toOrder">Заказать</button>%s'
           '<p class="fine">Цена без НДС. Точную стоимость, наличие и доставку подтвердим в ответ на заявку.</p></aside>' % (price_b, x["b"], calc_btn))

    rel = [y for y in CAT if y["c"] == c and y["a"] != a]
    if is_wood: rel = [y for y in rel if series(y) != series(x)][:6] or rel[:6]
    else: rel = rel[:6]
    related = ('<section class="rel"><div class="wrap"><h2>Ещё в разделе «%s»</h2><div class="grid">%s</div>'
               '<p class="more"><a class="btn ghost" href="%scatalog/%s/">Весь раздел</a></p></div></section>' % (esc(catc[2]), "".join(card(y, ROOT) for y in rel), ROOT, catc[1])) if rel else ""

    data = {"root": ROOT, "item": x, "kind": KIND[c], "photo": ph, "mask": PHOTO.get(a, "") in ("A172.jpg", "A38.jpg", "A503.jpg", "A504.jpg"),
            "paint": PAINT, "shop": {"telegram": SHOP["telegram"], "max": SHOP.get("max", ""), "phone": SHOP["phone"]}}
    if a in PROF: data["prof"] = PROF[a]
    elif a in PROF2: data["poly"] = PROF2[a]
    if is_wood: data["wood"] = wood_parts(x); data["tex"] = "img/tex/" + PHOTO[a] if PHOTO.get(a) else ""

    body = (header(ROOT) + '<main><div class="wrap">' + crumbs(crumb_items) +
            '<div class="ptop"><div><div class="ptitle"><h1>%s</h1><p class="lead">%s</p></div>' % (esc(x["n"]), esc(x["d"])) + tabs + stage + colors + prof_html + specs_html +
            '<div class="about"><h2>О товаре</h2>%s</div></div>%s</div></div>' % (about(x), buy) +
            related + lead_form(x) + "</main>" + footer(ROOT) +
            ('<script src="/mebel/_lib/three.min.js"></script><script src="/mebel/_lib/OrbitControls.js"></script>' if has3d else "") +
            '<script>window.P=%s</script><script src="%sassets/p.js?v=%s"></script></body></html>' % (json.dumps(data, ensure_ascii=False), ROOT, VER))
    return head(title(x), description(x), url, og_img, ld, ROOT) + body

# ---------- страница раздела ----------
def category_page(code, sl, menu, h1, intro):
    items = [x for x in CAT if x["c"] == code]
    url = "%s/catalog/%s/" % (BASE, sl)
    crumb_items = [("Главная", ROOT), (menu, "")]
    first_ph = next((photo(x["a"]) for x in items if photo(x["a"])), "")
    og_img = BASE + "/" + first_ph if first_ph else BASE + "/og.jpg"
    ld = '<script type="application/ld+json">%s</script>' % json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage", "name": h1, "url": url, "description": intro,
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": "%s/p/%s/" % (BASE, slug(x["a"])), "name": x["n"]} for i, x in enumerate(items)]}}, ensure_ascii=False)
    if code == "color":
        groups = []
        for s in ("2", "3", "5"):
            g = [x for x in items if series(x) == s]
            if g: groups.append('<h2 style="font-size:18px;margin:22px 0 10px">Серия %s — %s, %d шт в коробке</h2><div class="grid">%s</div>' % (s, WOOD_NAMES[s], g[0]["b"], "".join(card(x, ROOT) for x in g)))
        grid = "".join(groups)
    else:
        grid = '<div class="grid">%s</div>' % "".join(card(x, ROOT) for x in items)
    t = "%s — цены, размеры, купить в СПб | Наш декор" % h1
    desc = "%s %d артикулов с ценами и размерами. Доставка по Санкт-Петербургу и Ленобласти." % (intro.split(". ")[0] + ".", len(items))
    body = (header(ROOT) + '<main><div class="wrap">' + crumbs(crumb_items) +
            '<div class="head" style="margin-top:6px"><div><h1 style="font-size:clamp(24px,4.2vw,38px)">%s</h1><p class="catintro">%s</p></div></div>' % (esc(h1), esc(intro)) +
            sections_nav(code, ROOT) + grid +
            '<p class="note" style="margin-top:18px">Цены предварительные, за штуку, без НДС. Нажмите на товар — там фото, 3D, профиль, размеры, цена и заявка.</p></div>' % () +
            lead_form(None) + "</main>" + footer(ROOT) +
            '<script>window.P=%s</script><script src="%sassets/p.js?v=%s"></script></body></html>' % (json.dumps({"root": ROOT, "list": True, "shop": {"telegram": SHOP["telegram"], "max": SHOP.get("max", "")}}, ensure_ascii=False), ROOT, VER))
    return head(t, desc, url, og_img, ld, ROOT) + body

# ---------- сборка ----------
ROOT = "../../"
VER = datetime.datetime.now().strftime("%Y%m%d%H%M")
os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
open(os.path.join(SITE, "assets", "p.css"), "w", encoding="utf-8").write(BASE_CSS + "\n" + open(os.path.join(HERE, "p.css"), encoding="utf-8").read())
shutil.copy(os.path.join(HERE, "p.js"), os.path.join(SITE, "assets", "p.js"))

pdir = os.path.join(SITE, "p"); cdir = os.path.join(SITE, "catalog")
for d in (pdir, cdir):
    if os.path.isdir(d): shutil.rmtree(d)
urls = []
for x in CAT:
    d = os.path.join(pdir, slug(x["a"])); os.makedirs(d)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(product_page(x))
    urls.append(("%s/p/%s/" % (BASE, slug(x["a"])), "monthly", "0.7"))
for code, sl, menu, h1, intro in CATS:
    d = os.path.join(cdir, sl); os.makedirs(d)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(category_page(code, sl, menu, h1, intro))
    urls.insert(0, ("%s/catalog/%s/" % (BASE, sl), "weekly", "0.8"))
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
      '  <url><loc>%s/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>' % (BASE, TODAY)]
sm += ['  <url><loc>%s</loc><lastmod>%s</lastmod><changefreq>%s</changefreq><priority>%s</priority></url>' % (u, TODAY, f, p) for u, f, p in urls]
sm += ['  <url><loc>%s/%s</loc><lastmod>2026-11-09</lastmod><changefreq>yearly</changefreq><priority>%s</priority></url>' % (BASE, f, p) for f, p in (("oferta.html", "0.3"), ("privacy.html", "0.2"), ("consent.html", "0.2"))]
sm.append("</urlset>")
open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")
print("товаров: %d, разделов: %d, в sitemap: %d адресов, версия ассетов %s" % (len(CAT), len(CATS), len(urls) + 4, VER))
