"""Контур Узбекистана для карты в финале: Natural Earth 1:50m (world-atlas@2, TopoJSON) → uz_outline.json.
Запускается на GitHub один раз (если файла ещё нет), дальше файл лежит в ветке."""
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "uz_outline.json"
URLS = ["https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json",
        "https://unpkg.com/world-atlas@2/countries-50m.json"]


def main():
    if OUT.exists():
        return
    topo = None
    for u in URLS:
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                topo = json.loads(r.read())
            break
        except Exception as e:
            print("не скачалось:", u, e)
    if topo is None:
        sys.exit(0)            # без карты ролик всё равно соберётся
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append([round(x * sx + tx, 4), round(y * sy + ty, 4)])
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts += a if not pts else a[1:]
        return pts

    geo = next(g for g in topo["objects"]["countries"]["geometries"] if str(g.get("id")) == "860")
    polys = geo["arcs"] if geo["type"] == "MultiPolygon" else [geo["arcs"]]
    out = [[ring(r) for r in p] for p in polys]
    OUT.write_text(json.dumps({"source": "Natural Earth 1:50m via world-atlas@2", "polygons": out}))
    print("контур Узбекистана:", len(out), "частей,", sum(len(p[0]) for p in out), "точек")


main()
