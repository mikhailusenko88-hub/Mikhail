from playwright.sync_api import sync_playwright
import os
src = "file://" + os.path.abspath("brandbook.html")
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 794, "height": 1123})
    pg.goto(src, wait_until="networkidle", timeout=120000)
    pg.evaluate("() => document.fonts.ready.then(() => true)")
    pg.wait_for_timeout(3000)
    pg.pdf(path="Наш_декор_50_вариантов_логотипа.pdf", format="A4", print_background=True, prefer_css_page_size=True)
    os.makedirs("preview", exist_ok=True)
    try:
        pg.screenshot(path="preview/p1.png", full_page=True, clip={"x":0,"y":0,"width":794,"height":1123})
        pg.screenshot(path="preview/p2.png", full_page=True, clip={"x":0,"y":1123,"width":794,"height":1123})
    except Exception as e:
        print("screenshot failed", e)
    b.close()
print("ok")
