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

KIND = {"panel": "Реечная панель", "color": "Реечная панель цветная", "mold": "Молдинг для стен", "plinth": "Плинтус напольный", "cornice": "Потолочный плинтус", "corner": "Уголок декоративный"}
MATERIAL = "дюрополимер (полистирол высокой плотности)"   # так называют материал покупатели и продавцы плинтусов; подтверждение ARTDEC — за Михаилом
CATS = [  # код, адрес, название в меню, H1, вводный текст, title, description, FAQ
    ("panel", "reechnye-paneli", "Реечные панели", "Реечные панели и декоративные рейки для стен — белые, под покраску, 3 м",
     "Реечные панели (их же называют декоративные рейки для стен, стеновые панели-рейки, ламели) из дюрополимера — полистирола высокой плотности. "
     "Длина 3 метра — стена до потолка без горизонтальных стыков. Панели белые, под покраску: красятся в любой цвет вместе со стеной, стыки шпаклюются. "
     "Профили — от классических каннелюр до широких ламелей и глубоких пазов; объёмный рельеф для ТВ-зоны, изголовья кровати, прихожей и стены за диваном. "
     "Класс пожарной опасности Г2. Цены за штуку и за м², продаём поштучно и коробками, доставка по Санкт-Петербургу и Ленобласти.",
     "Реечные панели и декоративные рейки для стен — купить в СПб | Наш декор",
     "Реечные панели для стен из дюрополимера под покраску, длина 3 м: 18 профилей, цена за шт и за м², наличие в Санкт-Петербурге. 3D-просмотр, чертёж профиля, расчёт стены онлайн."),
    ("color", "paneli-pod-derevo", "Цветные и под дерево", "Реечные панели цветные и под дерево — серии 2, 3 и 5",
     "Цветные реечные панели с готовым декором под дерево (дуб, орех, тик) и под бетон на чёрной основе — красить не нужно. "
     "Три серии по числу реек на панели шириной 120 мм: серия 2 — две широкие, серия 3 — три, серия 5 — пять узких. Длина 3 м, дюрополимер. "
     "Декоры одной серии одинаковы по размеру и цене — их можно сочетать на одной стене. В коробке — один декор и одна серия.",
     "Цветные реечные панели и панели под дерево 3 м — купить в СПб | Наш декор",
     "Реечные панели под дерево и бетон на чёрной основе, 3 метра, 28 декоров в трёх сериях. Красить не нужно. Цена за шт и за м², доставка по СПб и Ленобласти, 3D-просмотр."),
    ("mold", "moldingi", "Молдинги", "Молдинги для стен под покраску: узкие, широкие, для рамок",
     "Настенные декоративные молдинги под покраску из дюрополимера — для рамок и панно на стенах, стыка обоев и покраски, зонирования. "
     "Ширина от 15 до 96 мм, длина 2 м (A611/3 и A611/4 — 3 м). У A35/2 и A157/2 сзади канал под кабель. "
     "Молдинг белый, красится в цвет стены или в контраст; углы запиливаются под 45°, стыки шпаклюются. Цены от 210 ₽ за штуку.",
     "Молдинги для стен под покраску — от 210 ₽, купить в СПб | Наш декор",
     "Декоративные молдинги для стен из дюрополимера под покраску: 28 профилей шириной 15–96 мм, длина 2 м. Цена за шт, наличие в Санкт-Петербурге, 3D и чертёж профиля."),
    ("plinth", "plintusy", "Плинтусы", "Плинтус напольный из дюрополимера — белый, под покраску, высота 65–150 мм",
     "Напольные плинтусы из дюрополимера (полистирола высокой плотности) под покраску: высота от 65 до 150 мм, длина 2 м. "
     "Плотный материал не крошится и не боится влажной уборки, красится в цвет стен или дверей. Модели A11-80, A11-100 и A12-100 — с пазом под LED-ленту (плинтус с подсветкой). "
     "Монтаж на клей, углы под 45°. Цены от 400 ₽ за штуку — дешевле аналогов из дюрополимера.",
     "Плинтус напольный дюрополимер 65–150 мм под покраску — купить в СПб | Наш декор",
     "Напольный плинтус из дюрополимера под покраску: белый, высота 65–150 мм, длина 2 м, есть с подсветкой. 28 моделей, цена за шт, наличие в Санкт-Петербурге, доставка по СПб и ЛО."),
    ("cornice", "karnizy", "Потолочный плинтус", "Потолочный плинтус (карниз) под покраску и под подсветку",
     "Потолочные плинтусы (карнизы) из дюрополимера под покраску — от компактного A38 20×20 мм до широкого A504, длина 2 м. "
     "Для скрытой LED-подсветки и «парящего» потолка — потолочный плинтус под подсветку A503 с нишей под ленту. "
     "Углы запиливаются под 45°, стык шпаклюется, красится в цвет потолка или стен.",
     "Потолочный плинтус из дюрополимера — широкий, под подсветку, под покраску — купить в СПб",
     "Потолочный плинтус (карниз) из дюрополимера под покраску, в том числе под LED-подсветку, длина 2 м. Цена за шт, наличие в Санкт-Петербурге, 3D и чертёж профиля."),
    ("corner", "ugolki", "Уголки", "Декоративные уголки для стен и стеновых панелей",
     "Декоративные уголки из дюрополимера под покраску для внешних углов 22×22 и 30×30 мм, длина 2 м — закрывают торцы реечных панелей на углу и защищают угол от сколов.",
     "Декоративные уголки для стеновых панелей — купить в СПб | Наш декор",
     "Декоративные уголки для внешних углов и торцов стеновых панелей, 22×22 и 30×30 мм, длина 2 м, под покраску. Цена за шт, доставка по СПб и Ленобласти."),
]
# FAQ по разделам: вопрос → ответ (на странице и в разметке FAQPage)
FAQ = {
    "panel": [
        ("Чем клеить реечные панели?", "Монтажным клеем для полистирола: жидкие гвозди на водной (акриловой) основе или MS-полимерный клей. Расход — примерно одна туба на 5 панелей. Клеи с растворителями (ацетон, толуол) нельзя — они разъедают полистирол."),
        ("Чем и как красить панели?", "Любой краской для стен на водной основе — акриловой или латексной, валиком или краскопультом. Панели поставляются белыми, под покраску; стыки между панелями перед покраской шпаклюются."),
        ("Как резать панели по высоте?", "Ножовкой с мелким зубом или электролобзиком. Панель 3 м закрывает стену до потолка целиком; при большей высоте панели стыкуются по длине."),
        ("Сколько панелей нужно на стену?", "Ширина стены ÷ ширина панели — это число панелей в ряд, плюс 10 % на подрезку. На странице каждой панели есть «3D · моя стена»: введите размеры — покажет стену и посчитает штуки, коробки и сумму."),
        ("Как доставка и оплата?", "Самовывоз со склада в Санкт-Петербурге бесплатно; по Петербургу — 1–2 дня, по Ленобласти — 1–3 дня после оплаты. Компаниям и ИП — по счёту; частным покупателям способ оплаты согласует менеджер при подтверждении заказа."),
    ],
    "color": [
        ("Нужно ли красить цветные панели?", "Нет. Рейки уже с декором под дерево или бетон, основа между ними матовая чёрная. Панель готова к монтажу."),
        ("Чем отличаются серии 2, 3 и 5?", "Числом реек на панели шириной 120 мм: серия 2 — две широкие, серия 3 — три, серия 5 — пять узких. Размер и цена у серий одинаковые."),
        ("Чем клеить панели под дерево?", "Жидкими гвоздями на водной основе или MS-полимерным клеем, примерно одна туба на 5 панелей. Клей с растворителем не подходит."),
        ("Можно ли сочетать разные декоры?", "Да: все декоры одной серии одинаковы по размеру, их можно чередовать на одной стене. В коробке — один декор."),
        ("Сколько панелей нужно на стену?", "Ширина стены ÷ 120 мм, плюс 10 % на подрезку. На странице панели — «3D · моя стена»: введите размеры, и расчёт появится сразу."),
    ],
    "mold": [
        ("Как запилить углы молдинга?", "Под 45° в стусле ножовкой с мелким зубом; стык промазывается клеем и шпаклюется."),
        ("Чем клеить молдинги на стену?", "Жидкими гвоздями на водной основе или акриловым монтажным клеем. Клеи с растворителями нельзя. Для рамок на обоях — на клей по обоям, предварительно разметив рамку."),
        ("Чем красить молдинги?", "Водно-дисперсионной краской для стен — в цвет стены или в контраст. Молдинг белый, под покраску."),
        ("Сколько молдинга нужно на рамку?", "Периметр рамки плюс запас 10 % на подрезку углов; длина молдинга — 2 м (A611/3 и A611/4 — 3 м)."),
        ("Есть ли молдинг с кабель-каналом?", "Да: A35/2 и A157/2 — сзади канал под кабель, остальное как у A35 и A157."),
    ],
    "plinth": [
        ("Что такое плинтус из дюрополимера?", "Дюрополимер — полистирол высокой плотности. Плинтус из него плотный и ровный, не крошится как пенопласт, не боится влажной уборки, красится любой краской для стен."),
        ("Как крепить напольный плинтус?", "На монтажный клей (жидкие гвозди на водной основе) к стене; углы запиливаются под 45° в стусле, стыки шпаклюются и красятся."),
        ("Какую высоту плинтуса выбрать?", "Под потолок 2,5 м обычно берут 65–80 мм, под 2,7–3 м — 100 мм и выше (A701, A704, A707, A004 119 мм, A702 150 мм)."),
        ("Есть ли плинтус с подсветкой и с кабель-каналом?", "С пазом под LED-ленту — A11-80, A11-100, A12-100. Кабель-канал есть у молдингов A35/2 и A157/2; у плинтусов провод прячется за полостью профиля."),
        ("Сколько плинтуса нужно?", "Периметр комнаты без дверных проёмов ÷ 2 м, плюс 10 % на подрезку; в коробке от 10 до 48 шт в зависимости от модели."),
    ],
    "cornice": [
        ("Как отрезать угол потолочного плинтуса?", "В стусле под 45°: для внутреннего угла — левая часть под 45° вправо, правая — влево; для внешнего наоборот. Без стусла — разметить по потолку и стене и отрезать по линиям. Стык шпаклюется."),
        ("Чем клеить потолочный плинтус?", "Жидкими гвоздями на водной основе или акриловым монтажным клеем — к стене и потолку; щели заполняются акриловым герметиком и красятся."),
        ("Какой карниз под LED-подсветку?", "A503 — потолочный плинтус под подсветку с нишей под ленту: крепится к стене с отступом от потолка, лента светит вверх — эффект парящего потолка."),
        ("Подходит ли для натяжного потолка?", "Да: карниз клеится только к стене, с зазором до натяжного полотна; под подсветку — A503."),
        ("Сколько нужно?", "Периметр потолка ÷ 2 м, плюс 10 % на подрезку углов."),
    ],
    "corner": [
        ("Для чего декоративный уголок?", "Закрыть торцы реечных панелей и обоев на внешнем углу и защитить угол от сколов. Полки 22×22 (A116) или 30×30 мм (A06)."),
        ("Чем клеить уголок?", "Жидкими гвоздями на водной основе или акриловым монтажным клеем; стыки с панелями шпаклюются и красятся вместе."),
        ("Чем красить?", "Любой краской для стен на водной основе, в цвет панелей или стены."),
        ("Сколько нужно?", "По высоте каждого внешнего угла: длина уголка 2 м, при потолке 2,7 м — две штуки на угол (с подрезкой)."),
        ("Есть ли внутренние уголки и торцевые планки?", "Пока нет — торец панели на внутреннем углу закрывается подрезкой и шпаклёвкой. Планки для стеновых панелей планируем добавить."),
    ],
}
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
    t = "%s — купить в СПб | Наш декор" % x["n"]
    if len(t) > 72: t = "%s — купить в СПб | Наш декор" % x["n"].split(", ")[0]
    return t
def m2(x): return x["r"] / (x["w"] / 1000.0 * x["l"] / 1000.0) if x.get("r") and x["c"] in ("panel", "color") else None
def description(x):
    price = ("Цена %s ₽ за шт (≈ %s ₽/м²), %d шт в коробке." % (fmt(x["r"]), fmt(m2(x)), x["b"])) if m2(x) else ("Цена %s ₽ за шт, %d шт в коробке." % (fmt(x["r"]), x["b"]) if x.get("r") else "%d шт в коробке." % x["b"])
    return "%s: %s. %s Наличие в Санкт-Петербурге или под заказ 3–4 недели, доставка по СПб и ЛО. %s" % (
        KIND[x["c"]], x["d"], price, "3D-просмотр, чертёж профиля и расчёт стены онлайн." if x["c"] in ("panel", "color") else "3D-просмотр, чертёж профиля и заявка на сайте.")

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
        '<a href="%scatalog/%s/"%s>%s</a>' % (root, s, ' aria-current="page"' if code == cur_code else "", esc(menu)) for code, s, menu, _, _, _, _ in CATS) + "</nav>"

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
            '<label class="f">E-mail — пришлём расчёт письмом (необязательно)<input type="email" id="lEmail" autocomplete="email" inputmode="email" placeholder="name@mail.ru"></label>'
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
    per = ("за шт · ≈ <span class=\"m2\">%s</span> ₽/м² · %d шт в коробке" % (fmt(m2(x)), x["b"])) if m2(x) else "за шт · %d шт в коробке" % x["b"]
    return ('<a class="card" href="%sp/%s/" data-p="%s"><div class="sw">%s</div><div class="in"><div class="eyebrow">%s</div><div class="art">%s</div><div class="d">%s</div>'
            '<div class="price">%s<small>%s</small><small class="stock">Под заказ, 3–4 недели</small></div></div></a>'
            % (root, slug(x["a"]), esc(x["a"]), img, esc(KIND[x["c"]]), esc(x["a"]), esc(x["d"]), price, per))

# ---------- тексты «о товаре» ----------
def about(x):
    c, a = x["c"], x["a"]
    out = []
    if c == "panel":
        out.append("<p>%s — стеновая реечная панель ARTDEC (декоративные рейки для стен, ламели) из дюрополимера — полистирола высокой плотности, %s. Длина 3 м закрывает стену до потолка без горизонтального стыка; при большей высоте панели стыкуются по длине. Куда ставят: ТВ-зона, изголовье кровати, прихожая, стена за диваном, перегородки.</p>" % (esc(a), esc(x["d"].split(",")[0])))
        out.append("<p>Панель поставляется белой, под покраску: красится в любой цвет вместе со стеной, стыки между панелями шпаклюются. Монтаж на клей (жидкие гвозди), в среднем один тюбик на 5 панелей.</p>")
        out.append("<p><b>Сколько нужно:</b> ширина стены ÷ %d мм = число панелей в ряд, плюс запас 10%% на подрезку. Точный расчёт с плинтусом и карнизом — в <a href=\"%s?panel=%s#calc\" style=\"color:var(--ink)\">3D-расчёте стены</a>.</p>" % (x["w"], ROOT, esc(a)))
    elif c == "color":
        s = series(x)
        out.append("<p>%s — реечная панель серии %s (%s) с готовым декором «%s» на чёрной основе. Красить не нужно: ламели уже с покрытием, основа между ними матовая чёрная. Размер %s.</p>" % (esc(a), s, WOOD_NAMES.get(s, "ламели"), esc(x["d"].split(",")[0]), dims(x)))
        out.append("<p>Все декоры серии %s одинаковы по размеру и цене — их можно сочетать на одной стене. В коробке %d шт одного декора. Монтаж на клей (жидкие гвозди).</p>" % (s, x["b"]))
        out.append("<p><b>Сколько нужно:</b> ширина стены ÷ %d мм = число панелей в ряд, плюс запас 10%% на подрезку. Точный расчёт — в <a href=\"%s?panel=%s#calc\" style=\"color:var(--ink)\">3D-расчёте стены</a>.</p>" % (x["w"], ROOT, esc(a)))
    elif c == "mold":
        extra = " Сзади — канал под кабель." if "канал" in x["d"] else ""
        extra += " Универсальный профиль: подходит как молдинг, плинтус или наличник." if "наличник" in x["d"] else ""
        out.append("<p>%s — настенный декоративный молдинг ARTDEC из дюрополимера под покраску, %s.%s Из него собирают рамки и панно на стенах, закрывают стык обоев и покраски, делят стену на зоны.</p>" % (esc(a), dims(x), extra))
        out.append("<p>Молдинг поставляется белым и красится вместе со стеной или в контрастный цвет. Монтаж на клей (жидкие гвозди), углы запиливаются под 45°. Для рамки считайте периметр плюс запас на подрезку.</p>")
    elif c == "plinth":
        led = " Паз под LED-ленту — подсветка пола." if "LED" in x["d"] else ""
        out.append("<p>%s — напольный плинтус ARTDEC из дюрополимера (полистирол высокой плотности) под покраску высотой %d мм, толщина %d мм, длина 2 м.%s Плотный, не крошится, не боится влажной уборки; красится в цвет стен, дверей или в контраст.</p>" % (esc(a), x["w"], x["t"], led))
        out.append("<p>Монтаж на клей (жидкие гвозди), углы запиливаются под 45°. Сколько нужно: периметр комнаты без дверных проёмов ÷ 2 м, плюс запас 10%% на подрезку. В коробке %d шт.</p>" % x["b"])
    elif c == "cornice":
        led = " Ниша под LED-ленту — скрытая подсветка, «парящий» потолок." if "LED" in x["d"] else ""
        out.append("<p>%s — потолочный плинтус (карниз) ARTDEC из дюрополимера под покраску, %s.%s Закрывает стык стены и потолка, подходит и для натяжного потолка (клеится к стене); красится в цвет потолка или стен.</p>" % (esc(a), dims(x), led))
        out.append("<p>Монтаж на клей, углы запиливаются под 45°. Сколько нужно: периметр потолка ÷ 2 м, плюс запас 10%% на подрезку. В коробке %d шт.</p>" % x["b"])
    else:
        out.append("<p>%s — декоративный уголок ARTDEC из дюрополимера под покраску для внешних углов, %s. Закрывает торцы реечных панелей и обоев на углу и защищает угол от сколов.</p>" % (esc(a), dims(x)))
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
             ("В коробке", "%d шт" % x["b"]), ("Материал", MATERIAL), ("Пожарная опасность", "класс Г2"),
             ("Покрытие", "декор «%s», красить не нужно" % x["d"].split(",")[0] if is_wood else "белый грунт, под покраску"),
             ("Производитель", "ARTDEC (Казахстан)")]
    if "LED" in x["d"]: specs.append(("Подсветка", "паз под LED-ленту"))
    if "канал" in x["d"]: specs.append(("Кабель-канал", "есть, сзади"))
    specs_html = '<div class="specs"><h2>Характеристики</h2><table>%s</table></div>' % "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(k), esc(v)) for k, v in specs)

    price_b = ('<b class="num" id="price">%s ₽</b>' % fmt(x["r"])) if x.get("r") else '<b id="price">По запросу</b>'
    calc_btn = ('<a class="btn ghost" id="toCalc" href="%s?panel=%s#calc">Рассчитать на стену в 3D</a>' % (ROOT, esc(a))) if c in ("panel", "color") else ""
    per = ("за штуку · ≈ <span id=\"pm2\">%s</span> ₽/м² · %d шт в коробке" % (fmt(m2(x)), x["b"])) if m2(x) else "за штуку · %d шт в коробке" % x["b"]
    buy = ('<aside class="buy" aria-label="Цена и заказ"><div class="price">%s<small>%s</small></div><div class="stock" id="stock">Под заказ, 3–4 недели</div>'
           '<div class="qty"><span class="qlbl">Количество</span><button type="button" id="qMinus" aria-label="Меньше">−</button><input type="number" id="qty" min="1" max="9999" value="1" inputmode="numeric" aria-label="Количество, штук">'
           '<span class="unit">шт</span><button type="button" id="qPlus" aria-label="Больше">+</button></div>'
           '<button type="button" class="btn sm ghost qbox" id="qBox">Взять коробкой — %d шт</button>'
           '<div class="total"><div><small>Итого, предварительно</small><b class="num" id="tSum">—</b></div><small id="tPack"></small></div>'
           '<button class="btn" type="button" id="toOrder">Заказать</button>%s'
           '<p class="fine">Цена без НДС. Точную стоимость, наличие и доставку подтвердим в ответ на заявку.</p></aside>' % (price_b, per, x["b"], calc_btn))

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
def category_page(code, sl, menu, h1, intro, ctitle, cdesc):
    items = [x for x in CAT if x["c"] == code]
    url = "%s/catalog/%s/" % (BASE, sl)
    crumb_items = [("Главная", ROOT), (menu, "")]
    first_ph = next((photo(x["a"]) for x in items if photo(x["a"])), "")
    og_img = BASE + "/" + first_ph if first_ph else BASE + "/og.jpg"
    faq = FAQ.get(code, [])
    faq_html = ('<section class="faq"><h2>Вопросы и ответы</h2>%s</section>' % "".join(
        '<details><summary>%s</summary><p>%s</p></details>' % (esc(q), esc(a_)) for q, a_ in faq)) if faq else ""
    ld = ('<script type="application/ld+json">%s</script>' % json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a_}} for q, a_ in faq]}, ensure_ascii=False)) if faq else ""
    ld += '<script type="application/ld+json">%s</script>' % json.dumps({
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
    t, desc = ctitle, cdesc
    body = (header(ROOT) + '<main><div class="wrap">' + crumbs(crumb_items) +
            '<div class="head" style="margin-top:6px"><div><h1 style="font-size:clamp(24px,4.2vw,38px)">%s</h1><p class="catintro">%s</p></div></div>' % (esc(h1), esc(intro)) +
            sections_nav(code, ROOT) + grid +
            '<p class="note" style="margin-top:18px">Цены предварительные, за штуку, без НДС. Нажмите на товар — там фото, 3D, профиль, размеры, цена и заявка.</p>' + faq_html + '</div>' +
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
for code, sl, menu, h1, intro, ctitle, cdesc in CATS:
    d = os.path.join(cdir, sl); os.makedirs(d)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(category_page(code, sl, menu, h1, intro, ctitle, cdesc))
    urls.insert(0, ("%s/catalog/%s/" % (BASE, sl), "weekly", "0.8"))
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
      '  <url><loc>%s/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>' % (BASE, TODAY)]
sm += ['  <url><loc>%s</loc><lastmod>%s</lastmod><changefreq>%s</changefreq><priority>%s</priority></url>' % (u, TODAY, f, p) for u, f, p in urls]
sm += ['  <url><loc>%s/%s</loc><lastmod>2026-11-09</lastmod><changefreq>yearly</changefreq><priority>%s</priority></url>' % (BASE, f, p) for f, p in (("oferta.html", "0.3"), ("privacy.html", "0.2"), ("consent.html", "0.2"))]
sm.append("</urlset>")
open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")
print("товаров: %d, разделов: %d, в sitemap: %d адресов, версия ассетов %s" % (len(CAT), len(CATS), len(urls) + 4, VER))
