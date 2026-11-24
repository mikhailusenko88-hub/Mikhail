#!/usr/bin/env python3
"""Наличие из фида Яндекс Товаров → на уже собранные страницы сайта «Наш декор» (с 24.11.2026).

Запуск:  python3 stock_pages.py <папка сайта 0f7s1eez>
Раз в час сразу после yml_prices.py (GitHub Actions «Авито — фид из CRM»): по available в <сайт>/yml.xml правит
  — на странице товара p/<артикул>/index.html разметку schema.org (availability: InStock / BackOrder)
    и текст «В наличии» / «Под заказ, 3–4 недели» в блоке цены;
  — в разделах catalog/*/index.html тот же текст на карточке товара.
Зачем: Яндекс Товары сверяют фид с сайтом — если фид говорит «в наличии», а страница «нет в наличии»,
товар могут не показать в Поиске. Точный остаток покупателю показывает p.js из CRM при заходе; в HTML числа нет,
поэтому страница меняется только когда товар появился на складе или закончился.
build.py (ветка mebel) при сборке делает то же самое из того же yml.xml.
Если yml.xml нет — ничего не делаем."""
import glob
import html
import os
import re
import sys

TXT_IN, TXT_OUT = "В наличии", "Под заказ, 3–4 недели"


def load_stock(site):
    """артикул (vendorCode) → (есть на складе, путь страницы p/<…>)"""
    path = os.path.join(site, "yml.xml")
    if not os.path.exists(path):
        return {}
    s = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'<offer id="[^"]+" available="(true|false)">(.*?)</offer>', s, re.S):
        body = m.group(2)
        a = re.search(r"<vendorCode>(.*?)</vendorCode>", body)
        u = re.search(r"<url>https://nashdekor\.ru/(p/[^<]+?)/?</url>", body)
        if a and u:
            out[html.unescape(a.group(1))] = (m.group(1) == "true", u.group(1))
    return out


def stock_small(ok):
    return '<small class="%s">%s</small>' % ("stock ok" if ok else "stock", TXT_IN if ok else TXT_OUT)


def main():
    site = sys.argv[1] if len(sys.argv) > 1 else "0f7s1eez"
    stock = load_stock(site)
    if not stock:
        print("наличие на страницах: yml.xml нет или пуст — страницы не трогаем")
        return
    changed = []

    # страницы товаров
    for art, (ok, rel) in stock.items():
        p = os.path.join(site, rel, "index.html")
        if not os.path.exists(p):
            continue
        h = open(p, encoding="utf-8").read()
        n = re.sub(r'"availability": "https://schema\.org/(?:InStock|BackOrder)"',
                   '"availability": "https://schema.org/%s"' % ("InStock" if ok else "BackOrder"), h)
        n = re.sub(r'<div class="stock(?: ok)?" id="stock">[^<]*</div>',
                   '<div class="%s" id="stock">%s</div>' % ("stock ok" if ok else "stock", TXT_IN if ok else TXT_OUT), n)
        if n != h:
            open(p, "w", encoding="utf-8").write(n)
            changed.append("/%s/" % rel)

    # разделы: <div class="card" data-p="АРТИКУЛ">…<small class="stock">…</small>
    def card(m):
        st = stock.get(html.unescape(m.group(1)))
        if st is None:
            return m.group(0)
        return re.sub(r'<small class="stock(?: ok)?">[^<]*</small>', stock_small(st[0]), m.group(0), count=1)

    for p in sorted(glob.glob(os.path.join(site, "catalog", "*", "index.html"))):
        h = open(p, encoding="utf-8").read()
        n = re.sub(r'<div class="card" data-p="([^"]+)">.*?<small class="stock(?: ok)?">[^<]*</small>', card, h, flags=re.S)
        if n != h:
            open(p, "w", encoding="utf-8").write(n)
            changed.append("/" + os.path.relpath(os.path.dirname(p), site) + "/")

    n_in = sum(1 for ok, _ in stock.values() if ok)
    print("наличие на страницах: в фиде %d товаров, в наличии %d; изменено страниц: %d%s"
          % (len(stock), n_in, len(changed), (" — " + ", ".join(changed[:20])) if changed else ""))


if __name__ == "__main__":
    main()
