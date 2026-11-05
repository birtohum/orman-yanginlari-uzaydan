"""veri/tespitler.csv'den site verilerini üretir -> site/veri/

Kullanım: python uret.py
"""
import datetime as dt, json, os, re, unicodedata
from collections import defaultdict

from shapely.geometry import mapping, shape

import olaylar, tespit

SITE = "site/veri"
SINIF_NO = {"orman": 0, "tarim": 1, "diger": 2}


def slug(s):
    s = s.replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def yaz(ad, veri):
    os.makedirs(os.path.dirname(f"{SITE}/{ad}"), exist_ok=True)
    with open(f"{SITE}/{ad}", "w", encoding="utf8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))


def harita_kaynagi(yil):
    return "V" if yil >= 2012 else "M"


def sinirlar():
    fc = json.load(open("veri/ham/tur_adm1.geojson", encoding="utf8"))
    out = []
    for f in fc["features"]:
        g = shape(f["geometry"]).simplify(0.01, preserve_topology=True)
        m = mapping(g)
        polys = m["coordinates"] if m["type"] == "MultiPolygon" else [m["coordinates"]]
        halkalar = [[[round(x, 3), round(y, 3)] for x, y in p[0]] for p in polys if len(p[0]) > 3]
        out.append({"ad": f["properties"]["shapeName"], "h": halkalar})
    return out


def main():
    t = tespit.oku()
    bugun = dt.date.today().isoformat()
    son_tarih = max(r["tarih"] for r in t)
    yillik = {"V": defaultdict(lambda: defaultdict(int)), "M": defaultdict(lambda: defaultdict(int))}
    iller = defaultdict(lambda: {"V": defaultdict(lambda: [0, 0]), "M": defaultdict(lambda: [0, 0])})
    harita = defaultdict(lambda: defaultdict(int))
    aralik = {}
    aylik = defaultdict(lambda: defaultdict(int))
    for r in t:
        y = int(r["tarih"][:4]); k = r["kaynak"]; ay = int(r["tarih"][5:7])
        yillik[k][y]["toplam"] += 1; yillik[k][y][r["sinif"]] += 1
        c = iller[r["il"]][k][y]; c[0] += 1; c[1] += r["sinif"] == "orman"
        if k == "V":
            aylik[r["sinif"]][ay] += 1
        if harita_kaynagi(y) == k:
            a = aralik.setdefault(y, [r["tarih"], r["tarih"]])
            a[0] = min(a[0], r["tarih"]); a[1] = max(a[1], r["tarih"])
            harita[y][(round(r["lon"] * 100), round(r["lat"] * 100), ay, SINIF_NO[r["sinif"]])] += 1
    bilgi = json.load(open("veri/tespit_bilgi.json"))
    ozet = {
        "guncelleme": bugun, "son_tespit": son_tarih,
        "yillik": {k: {y: dict(v) for y, v in sorted(d.items())} for k, d in yillik.items()},
        "aylik_viirs": {s: [aylik[s][m] for m in range(1, 13)] for s in ("orman", "tarim", "diger")},
        "suzme": bilgi,
        "harita_yillari": sorted(harita),
        "yil_araligi": {y: aralik[y] for y in sorted(aralik)},
    }
    yaz("ozet.json", ozet)
    yaz("iller.json", {il: {k: {y: v for y, v in sorted(d[k].items())} for k in d} for il, d in sorted(iller.items())})
    for y, d in harita.items():
        yaz(f"harita/{y}.json", {"kaynak": harita_kaynagi(y), "n": [[*a, n] for a, n in sorted(d.items())]})
    yaz("sinirlar.json", sinirlar())

    # büyük yangın adayları (uydu.py ölçer)
    ad = olaylar.buyukler(t)
    for o in ad:
        o["id"] = f"{o['bas']}-{slug(o['ilce'])}"
    json.dump(ad, open("veri/olay_adaylari.json", "w", encoding="utf8"), ensure_ascii=False)
    if os.path.exists("veri/olaylar.json"):
        ol = json.load(open("veri/olaylar.json", encoding="utf8"))
        yaz("olaylar.json", sorted(ol, key=lambda o: -o["yanik_ha"]))
    print("son tespit", son_tarih, "| harita yılları", len(harita), "| büyük yangın adayı", len(ad))


if __name__ == "__main__":
    main()
