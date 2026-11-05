"""VIIRS tespitlerini yer ve zamanda kümeleyerek büyük yangınları bulur.

İki tespit, aralarında en fazla BAG_KM ve en fazla BAG_GUN gün varsa aynı yangın sayılır
(bağlantı zincirleme: A–B, B–C bağlıysa A, B, C aynı kümededir).
Kümenin büyüklüğü: kapladığı ~375 m'lik farklı hücre sayısı (aynı yerin tekrar tekrar
görülmesi büyüklüğü şişirmesin diye tespit sayısı yerine).
"""
import math
from collections import Counter, defaultdict
import datetime as dt
import numpy as np

BAG_KM = 1.5
BAG_GUN = 2
HUCRE = 0.004   # ~375 m


class Birlik:
    def __init__(self, n):
        self.p = list(range(n))

    def bul(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]; i = self.p[i]
        return i

    def birlestir(self, a, b):
        a, b = self.bul(a), self.bul(b)
        if a != b:
            self.p[b] = a


def kumele(noktalar, bag_km=BAG_KM, bag_gun=BAG_GUN):
    """noktalar: dict listesi (lat, lon, tarih 'YYYY-MM-DD'). Dönüş: her nokta için küme no."""
    n = len(noktalar)
    b = Birlik(n)
    adim = bag_km / 111.0
    gun = [dt.date.fromisoformat(r["tarih"]).toordinal() for r in noktalar]
    izgara = defaultdict(list)
    for i, r in enumerate(noktalar):
        izgara[(int(math.floor(r["lon"] / adim)), int(math.floor(r["lat"] / adim)))].append(i)
    for (gx, gy), uyeler in izgara.items():
        aday = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                aday += izgara.get((gx + dx, gy + dy), [])
        for i in uyeler:
            ri = noktalar[i]; c = math.cos(math.radians(ri["lat"]))
            for j in aday:
                if j <= i:
                    continue
                if abs(gun[i] - gun[j]) > bag_gun:
                    continue
                rj = noktalar[j]
                d = 111.32 * math.hypot((rj["lon"] - ri["lon"]) * c, rj["lat"] - ri["lat"])
                if d <= bag_km:
                    b.birlestir(i, j)
    return [b.bul(i) for i in range(n)]


def ozetle(noktalar, etiket):
    gruplar = defaultdict(list)
    for r, e in zip(noktalar, etiket):
        gruplar[e].append(r)
    olay = []
    for e, g in gruplar.items():
        hucre = {(int(math.floor(r["lon"] / HUCRE)), int(math.floor(r["lat"] / HUCRE))) for r in g}
        lat = [r["lat"] for r in g]; lon = [r["lon"] for r in g]
        il = Counter(r["il"] for r in g).most_common(1)[0][0]
        ilce = Counter(r["ilce"] for r in g if r["il"] == il).most_common(1)[0][0]
        olay.append({
            "bas": min(r["tarih"] for r in g), "son": max(r["tarih"] for r in g),
            "tespit": len(g), "hucre": len(hucre),
            "orman_payi": round(sum(r["sinif"] == "orman" for r in g) / len(g), 3),
            "il": il, "ilce": ilce,
            "kutu": [min(lon), min(lat), max(lon), max(lat)],
            "noktalar": [[round(r["lon"], 5), round(r["lat"], 5)] for r in g],
        })
    olay.sort(key=lambda o: -o["hucre"])
    return olay


def buyukler(tespitler, bas="2016-06-01", en_az_orman=0.4, adet=40):
    v = [r for r in tespitler if r["kaynak"] == "V" and r["tarih"] >= bas]
    olay = ozetle(v, kumele(v))
    return [o for o in olay if o["orman_payi"] >= en_az_orman][:adet]
