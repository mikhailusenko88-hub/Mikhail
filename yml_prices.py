#!/usr/bin/env python3
"""Цены и наличие из CRM → товарный фид Яндекс Товаров (yml.xml сайта «Наш декор»).

Запуск:  python3 yml_prices.py <путь/к/yml.xml> [--crm=https://crm.nashdekor.ru/api/catalog | --crm-json=файл]
Фид собирает сайт (nashdekor-build/build.py, ветка mebel) с ценами из каталога; этот скрипт раз в час
(GitHub Actions «Авито — фид из CRM») ставит в него цены и свободные остатки из CRM:
  <price> — цена CRM; available="true" и <count> — если свободный остаток > 0, иначе available="false" (под заказ 3–4 недели).
Если CRM не ответила — файл не трогаем. Меняет файл только если что-то изменилось (дату в шапке — тогда же)."""
import datetime
import json
import re
import sys
import urllib.request

CRM_URL = "https://crm.nashdekor.ru/api/catalog"


def yml_id(a):
    return re.sub(r"[^A-Za-z0-9-]", "", a.replace("/", "-").replace(" ", ""))


def load_crm(src):
    try:
        if src.startswith("http"):
            req = urllib.request.Request(src, headers={"User-Agent": "nashdekor-yml-feed/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
        else:
            data = json.load(open(src, encoding="utf-8"))
    except Exception as e:
        sys.exit(f"CRM не ответила ({src}): {e} — фид Яндекс Товаров не меняем")
    items = data.get("items") if isinstance(data, dict) else None
    if not items or data.get("ok") is False:
        sys.exit("CRM вернула пустой каталог — фид Яндекс Товаров не меняем")
    return {yml_id(str(k)): v for k, v in items.items()}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    src = CRM_URL
    for a in sys.argv[2:]:
        if a.startswith("--crm="):
            src = a.split("=", 1)[1]
        elif a.startswith("--crm-json="):
            src = a.split("=", 1)[1]
    crm = load_crm(src)
    s = open(path, encoding="utf-8").read()
    changed = {"price": 0, "avail": 0}
    seen = set()

    def fix(m):
        block = m.group(0)
        oid = m.group(1)
        c = crm.get(oid)
        if not c:
            return block
        seen.add(oid)
        p, q = c.get("p"), c.get("q") or 0
        new = block
        if isinstance(p, (int, float)) and p > 0:
            new = re.sub(r"<price>[^<]*</price>", "<price>%d</price>" % int(round(p)), new, count=1)
        avail = "true" if q > 0 else "false"
        new = re.sub(r'available="(true|false)"', 'available="%s"' % avail, new, count=1)
        new = re.sub(r"\n\s*<count>\d+</count>", "", new)
        if q > 0:
            new = new.replace("</currencyId>", "</currencyId>\n      <count>%d</count>" % int(q), 1)
        if new != block:
            if re.search(r"<price>[^<]*</price>", new).group(0) != re.search(r"<price>[^<]*</price>", block).group(0):
                changed["price"] += 1
            if 'available="%s"' % avail not in block:
                changed["avail"] += 1
        return new

    out = re.sub(r'<offer id="([^"]+)"[^>]*>.*?</offer>', fix, s, flags=re.S)
    print(f"yml.xml: предложений {len(re.findall(r'<offer ', s))}, найдено в CRM {len(seen)}, "
          f"цена изменилась {changed['price']}, наличие {changed['avail']}")
    if out != s:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%dT%H:%M:%S+03:00")
        out = re.sub(r'<yml_catalog date="[^"]*">', '<yml_catalog date="%s">' % now, out, count=1)
        open(path, "w", encoding="utf-8").write(out)
        print("yml.xml обновлён")
    else:
        print("yml.xml без изменений")


if __name__ == "__main__":
    main()
