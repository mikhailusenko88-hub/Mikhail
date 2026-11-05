"""Все города и машины, которые зрители могут попросить в комментариях, и узнавание их в любом написании.

Один город — одна запись, сколько бы способов написать его ни было: Qoʻqon, Qo'qon, Qoqon, Kokand, Коканд, Қўқон…
Сравниваются «скелеты» слов: всё в латиницу, q→k, x→h, o→a, e→i, двойные буквы — одна и т.п.
Поэтому город, который уже есть в гонке, второй раз под другим написанием не добавится.
"""
import difflib
import re

# ---------- города: узбекский, русский, широта, долгота, другие написания ----------
CITY_POOL = [
    # уже в гонке (race_leagues.CITIES) — здесь ради узнавания других написаний
    ("Toshkent", "Ташкент", 41.31, 69.28, "Tashkent Tashkand Тошкент Ташкенд"),
    ("Samarqand", "Самарканд", 39.65, 66.96, "Samarkand Самарқанд Samarkant"),
    ("Buxoro", "Бухара", 39.77, 64.42, "Bukhara Buhara Бухоро Buxara"),
    ("Namangan", "Наманган", 41.00, 71.67, ""),
    ("Andijon", "Андижан", 40.78, 72.34, "Andijan Андижон Andizhan"),
    ("Fargʻona", "Фергана", 40.38, 71.79, "Fergana Ferghana Фарғона Fargana"),
    ("Qoʻqon", "Коканд", 40.53, 70.94, "Kokand Qoqand Қўқон Коканд Kokon"),
    ("Margʻilon", "Маргилан", 40.47, 71.72, "Margilan Марғилон"),
    ("Nukus", "Нукус", 42.46, 59.60, "Nokis Нөкис Nókis Qoraqalpogʻiston Qoraqalpogiston Каракалпакстан Karakalpakstan"),
    ("Qarshi", "Карши", 38.86, 65.79, "Karshi Қарши Qashqadaryo Кашкадарья Kashkadarya"),
    ("Termiz", "Термез", 37.22, 67.28, "Termez Термиз Surxondaryo Сурхандарья Surkhandarya"),
    ("Jizzax", "Джизак", 40.12, 67.84, "Jizzakh Djizak Jizak Жиззах Джиззах"),
    ("Navoiy", "Навои", 40.10, 65.37, "Navoi Навоий"),
    ("Urganch", "Ургенч", 41.55, 60.63, "Urgench Урганч Xorazm Хорезм Khorezm Хоразм"),
    ("Xiva", "Хива", 41.38, 60.36, "Khiva Hiva"),
    ("Guliston", "Гулистан", 40.49, 68.78, "Gulistan"),
    ("Chirchiq", "Чирчик", 41.47, 69.58, "Chirchik"),
    ("Olmaliq", "Алмалык", 40.84, 69.60, "Almalyk Almalik Олмалиқ"),
    ("Angren", "Ангрен", 41.02, 70.14, ""),
    ("Shahrisabz", "Шахрисабз", 39.06, 66.83, "Shakhrisabz Шаҳрисабз"),
    ("Asaka", "Асака", 40.64, 72.24, ""),
    ("Zarafshon", "Зарафшан", 41.57, 64.20, "Zarafshan"),
    # можно добавить по просьбе
    ("Denov", "Денау", 38.27, 67.90, "Denau Денов"),
    ("Chust", "Чуст", 41.00, 71.24, ""),
    ("Kattaqoʻrgʻon", "Каттакурган", 39.90, 66.26, "Kattakurgan"),
    ("Bekobod", "Бекабад", 40.22, 69.27, "Bekabad"),
    ("Urgut", "Ургут", 39.40, 67.24, ""),
    ("Gʻijduvon", "Гиждуван", 40.10, 64.68, "Gijduvan Гиждувон"),
    ("Xonqa", "Ханка", 41.47, 60.78, "Khanka"),
    ("Beruniy", "Беруни", 41.69, 60.75, "Beruni"),
    ("Quvasoy", "Кувасай", 40.30, 71.98, "Kuvasay Kuvasoy"),
    ("Nurafshon", "Нурафшан", 41.05, 69.35, "Nurafshan"),
    ("Yangiyoʻl", "Янгиюль", 41.11, 69.05, "Yangiyul Yangiyo'l"),
    ("Ohangaron", "Ахангаран", 40.91, 69.64, "Akhangaran Ahangaran"),
    ("Yangiyer", "Янгиер", 40.27, 68.82, ""),
    ("Sirdaryo", "Сырдарья", 40.84, 68.66, "Syrdarya Sirdarya"),
    ("Zomin", "Заамин", 39.96, 68.40, "Zaamin Zamin"),
    ("Gʻallaorol", "Галляарал", 40.03, 67.59, "Gallyaaral Gallaaral"),
    ("Kogon", "Каган", 39.72, 64.55, "Kagan"),
    ("Qorakoʻl", "Каракуль", 39.50, 63.85, "Karakul"),
    ("Uchquduq", "Учкудук", 42.16, 63.56, "Uchkuduk"),
    ("Nurota", "Нурата", 40.56, 65.69, "Nurata"),
    ("Koson", "Касан", 39.04, 65.58, "Kasan"),
    ("Kitob", "Китаб", 39.12, 66.88, "Kitab"),
    ("Yakkabogʻ", "Яккабаг", 38.98, 66.68, "Yakkabag"),
    ("Qamashi", "Камаши", 38.82, 66.46, "Kamashi"),
    ("Sherobod", "Шерабад", 37.67, 67.01, "Sherabad"),
    ("Shoʻrchi", "Шурчи", 38.00, 67.79, "Shurchi"),
    ("Boysun", "Байсун", 38.21, 67.20, "Baysun"),
    ("Qumqoʻrgʻon", "Кумкурган", 37.83, 67.58, "Kumkurgan"),
    ("Xazorasp", "Хазарасп", 41.32, 61.08, "Khazarasp Hazarasp"),
    ("Toʻrtkoʻl", "Турткуль", 41.55, 61.00, "Turtkul"),
    ("Xoʻjayli", "Ходжейли", 42.40, 59.45, "Khodjeyli Hojeli Xojeli"),
    ("Moʻynoq", "Муйнак", 43.77, 59.02, "Muynak Moynaq"),
    ("Chimboy", "Чимбай", 42.93, 59.78, "Chimbay"),
    ("Qoʻngʻirot", "Кунград", 43.05, 58.84, "Kungrad Qongirat"),
    ("Taxiatosh", "Тахиаташ", 42.32, 59.60, "Takhiatash"),
    ("Rishton", "Риштан", 40.36, 71.28, "Rishtan"),
    ("Quva", "Кува", 40.52, 72.07, "Kuva"),
    ("Oltiariq", "Алтыарык", 40.39, 71.48, "Altyaryk"),
    ("Beshariq", "Бешарык", 40.43, 70.61, "Besharyk"),
    ("Xonobod", "Ханабад", 40.80, 73.00, "Khanabad"),
    ("Shahrixon", "Шахрихан", 40.71, 72.06, "Shakhrikhan"),
    ("Qoʻrgʻontepa", "Кургантепа", 40.73, 72.76, "Kurgantepa"),
    ("Paxtaobod", "Пахтаабад", 40.93, 72.50, "Pakhtaabad"),
    ("Uchqoʻrgʻon", "Учкурган", 41.11, 72.08, "Uchkurgan"),
    ("Kosonsoy", "Касансай", 41.25, 71.55, "Kasansay"),
    ("Toʻraqoʻrgʻon", "Туракурган", 41.00, 71.51, "Turakurgan"),
    ("Chortoq", "Чартак", 41.07, 71.82, "Chartak"),
    ("Pop", "Пап", 40.87, 71.11, "Pap"),
    ("Piskent", "Пскент", 40.90, 69.35, "Pskent"),
    ("Parkent", "Паркент", 41.29, 69.68, ""),
    ("Gʻazalkent", "Газалкент", 41.56, 69.77, "Gazalkent"),
    ("Jomboy", "Джамбай", 39.70, 67.09, "Jambay Dzhambay"),
    ("Ishtixon", "Иштыхан", 39.97, 66.49, "Ishtikhan"),
]

# ---------- машины: название, по-русски, кузов, другие написания ----------
CAR_POOL = [
    ("Cobalt", "Cobalt", "sedan", "Кобальт Kobalt"),
    ("Gentra", "Gentra", "sedan", "Жентра Джентра Gentira"),
    ("Nexia", "Nexia", "sedan", "Нексия Neksiya Nexiya Nexia3 Нексия3"),
    ("Lacetti", "Lacetti", "hatch", "Ласетти Лачетти Lasetti Lacheti Lachetti"),
    ("Spark", "Spark", "mini", "Спарк"),
    ("Matiz", "Matiz", "mini", "Матиз Matis"),
    ("Tico", "Tico", "mini", "Тико Tiko"),
    ("Damas", "Damas", "van", "Дамас"),
    ("Labo", "Labo", "pickup", "Лабо"),
    ("Malibu", "Malibu", "sedan", "Малибу"),
    ("Captiva", "Captiva", "suv", "Каптива Kaptiva"),
    ("Tracker", "Tracker", "suv", "Трекер Treker Trekker"),
    ("Onix", "Onix", "sedan", "Оникс Oniks"),
    ("Equinox", "Equinox", "suv", "Эквинокс Ekvinoks"),
    ("Tahoe", "Tahoe", "suv", "Тахо Taho"),
    ("Epica", "Epica", "sedan", "Эпика Epika"),
    ("Kia K5", "Kia K5", "sedan", "K5 КиаК5 К5"),
    ("BYD Song", "BYD Song", "suv", "БИДСонг BYDSongPlus SongPlus"),
    ("Chery Tiggo", "Chery Tiggo", "suv", "Tiggo Тигго Тиго"),
    ("Jiguli", "Жигули", "classic", "Жигуль Jigul Lada Лада Vaz Ваз Шестерка Oltilik"),
    # можно добавить по просьбе
    ("Kia Sonet", "Kia Sonet", "suv", "Sonet Сонет"),
    ("Kia Seltos", "Kia Seltos", "suv", "Seltos Селтос"),
    ("Hyundai Elantra", "Hyundai Elantra", "sedan", "Elantra Элантра"),
    ("Hyundai Sonata", "Hyundai Sonata", "sedan", "Sonata Соната"),
    ("Toyota Camry", "Toyota Camry", "sedan", "Camry Камри Kamri"),
    ("Lada Vesta", "Lada Vesta", "sedan", "Vesta Веста"),
    ("Niva", "Нива", "suv", "Нива"),
    ("Moskvich", "Москвич", "classic", "Москвич Moskvich"),
    ("Volga", "Волга", "classic", "Волга"),
    ("BYD Chazor", "BYD Chazor", "sedan", "Chazor Чазор"),
    ("Haval Jolion", "Haval Jolion", "suv", "Jolion Джолион Haval Хавал"),
    ("Chery Arrizo", "Chery Arrizo", "sedan", "Arrizo Арризо"),
    ("Tesla", "Tesla", "sedan", "Тесла"),
    ("Mercedes", "Mercedes", "sedan", "Мерседес Мерс Mers Merc"),
    ("BMW", "BMW", "sedan", "БМВ Bmv"),
    ("Li Auto", "Li Auto", "suv", "LiAuto Lixiang Лисян"),
    ("Zeekr", "Zeekr", "suv", "Зикр Zeeker"),
    ("Isuzu", "Isuzu", "van", "Исузу"),
    ("Orlando", "Orlando", "van", "Орландо"),
    ("Monza", "Monza", "sedan", "Монза"),
    ("Trax", "Trax", "suv", "Тракс Траx"),
]

# Слова, которые в комментариях почти всегда значат не город/машину (узб. «книга», «поздравляю»…)
STOP = {"kitob", "китоб", "pop", "поп", "muborak", "muborak", "guzor", "lada", "лада", "song", "сонг", "vaz", "ваз"}

_CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
        "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "ң": "n", "о": "o", "ө": "o", "ў": "o", "п": "p",
        "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u", "ұ": "u", "ф": "f", "х": "x", "ҳ": "h", "һ": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "і": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ә": "a"}


def skel(s):
    """«Скелет» слова: одинаковый для Qoʻqon / Qoqon / Kokand / Коканд."""
    s = s.lower()
    s = "".join(_CYR.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9]", "", s)
    for a, b in (("dzh", "j"), ("dj", "j"), ("zh", "j"), ("kh", "h"), ("sh", "$"), ("ch", "%"), ("ts", "s"),
                 ("yo", "o"), ("yu", "u"), ("ya", "a"), ("ye", "e")):
        s = s.replace(a, b)
    s = s.replace("q", "k").replace("x", "h").replace("o", "a").replace("e", "i").replace("y", "i").replace("w", "v")
    s = re.sub(r"(.)\1+", r"\1", s)
    if len(s) > 4 and s.endswith("i") and not s.endswith("ii"):
        s = s[:-1]                      # Navoiy / Навои
    return s


def _index(pool):
    idx = []
    for row in pool:
        key, ru = row[0], row[1]
        names = [key, ru] + (row[-1].split() if row[-1] else [])
        for n in names:
            k = skel(n)
            if k:
                idx.append((k, key))
    return idx


CITY_INDEX = _index(CITY_POOL)
CAR_INDEX = _index(CAR_POOL)
CITY_BY_KEY = {r[0]: r for r in CITY_POOL}
CAR_BY_KEY = {r[0]: r for r in CAR_POOL}


# окончания: Toshkentdan, Andijonlikman, Samarqandga, из Ташкента, андижанцы…
SUFFIX = {skel(x) for x in ("dan", "ga", "da", "lik", "liklar", "likman", "likmiz", "man", "miz", "ning", "ni", "dagi",
                            "lar", "liman", "chi", "dan man", "a", "e", "u", "om", "ets", "tsy", "skiy", "skaya", "ski")}


def _match(word, index, force=False):
    k = skel(word)
    if len(k) < 3 or (not force and word.lower().replace("ʻ", "").replace("'", "") in STOP):
        return None
    for kk, key in index:
        if kk == k:
            return key
    # город + окончание (самое длинное совпадение начала)
    best = None
    for kk, key in index:
        if len(kk) >= 4 and k.startswith(kk) and (best is None or len(kk) > len(best[0])):
            rest = k[len(kk):]
            if rest in SUFFIX or (len(kk) >= 6 and len(rest) <= 6):
                best = (kk, key)
    if best:
        return best[1]
    if len(k) < 5:
        return None
    key_, score = None, 0.0
    for kk, key in index:
        if len(kk) >= 5:
            r = difflib.SequenceMatcher(None, k, kk).ratio()
            if r > score:
                key_, score = key, r
    return key_ if score >= 0.86 else None


def find(text, league):
    """Города (league='cities') или машины ('cars') из текста комментария: список ключей без повторов.
    Длинные комментарии (больше 15 слов) не разбираем — там обычно не просьба."""
    index = CITY_INDEX if league == "cities" else CAR_INDEX
    words = re.findall(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳӘәӨөҰұҮүІіҢңҺһ0-9ʻʼ'’`]+", text or "")
    if not words or len(words) > 15:
        return []
    out = []
    # «Kitob shahri», «город Пап» — слово из STOP рядом со словом «город» всё-таки город
    city_word = {skel(x) for x in ("shahri", "shahar", "shahrim", "город", "tumani", "shaxri")}
    near_city = {i for i, w in enumerate(words) if skel(w) in city_word}
    grams = [(w, (i - 1 in near_city or i + 1 in near_city)) for i, w in enumerate(words)] + \
            [(a + b, False) for a, b in zip(words, words[1:])]
    for g, force in grams:
        key = _match(g, index, force)
        if key and key not in out:
            out.append(key)
    return out
