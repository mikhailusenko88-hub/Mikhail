"""Одноразово: контур Казахстана из world-atlas (Natural Earth 1:50m) -> status/kz_outline.json"""
import json, urllib.request
url = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json"
topo = json.load(urllib.request.urlopen(url, timeout=60))
sc, tr = topo["transform"]["scale"], topo["transform"]["translate"]
arcs = []
for arc in topo["arcs"]:
    x = y = 0; pts = []
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((round(x * sc[0] + tr[0], 4), round(y * sc[1] + tr[1], 4)))
    arcs.append(pts)
def ring(ids):
    out = []
    for i in ids:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        out += a if not out else a[1:]
    return out
geoms = topo["objects"]["countries"]["geometries"]
kz = [g for g in geoms if str(g.get("id")) == "398"][0]
polys = kz["arcs"] if kz["type"] == "MultiPolygon" else [kz["arcs"]]
res = {"source": "Natural Earth 1:50m via world-atlas@2", "polygons": [[ring(r) for r in p] for p in polys]}
json.dump(res, open("status/kz_outline.json", "w"))
print("polygons", len(res["polygons"]), "points", sum(len(r) for p in res["polygons"] for r in p))
