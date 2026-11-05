"""Tüm tespitleri okur, süzer, il/ilçe ve arazi sınıfı ekler -> veri/tespitler.csv

Kullanım: python tespit.py
"""
import csv, os
from collections import Counter
import numpy as np

import firms, guncel
from konum import Arazi, Bolgeler

CIKTI = "veri/tespitler.csv"
ALANLAR = ["kaynak", "tarih", "saat", "lat", "lon", "frp", "gece", "il", "ilce", "sinif"]
# Arazi sınıfı için bakılan yarıçap: pikselin yarısı kadar
YARICAP = {"V": 200, "M": 500}


def hepsi():
    arsiv = firms.arsiv_oku()
    var = {(r["kaynak"], r["tarih"][:4]) for r in arsiv}
    nrt = [r for r in guncel.oku() if (r["kaynak"], r["tarih"][:4]) not in var]
    sabit = firms.sabit_hucreler(arsiv)
    ham = len(arsiv) + len(nrt)
    sec = firms.suz(firms.tekille(arsiv + nrt), sabit)
    tip = Counter(r["tip"] for r in arsiv)
    return sec, {"ham": ham, "arsiv_tip": dict(tip), "nrt": len(nrt), "sabit_hucre": len(sabit)}


def isle():
    sec, bilgi = hepsi()
    lon = np.array([r["lon"] for r in sec]); lat = np.array([r["lat"] for r in sec])
    il = Bolgeler.dosyadan("veri/ham/tur_adm1.geojson").ata(lon, lat)
    ilce = Bolgeler.dosyadan("veri/ham/tur_adm2.geojson").ata(lon, lat)
    arazi = Arazi()
    sinif = np.empty(len(sec), dtype=object)
    for k, r in YARICAP.items():
        m = np.array([s["kaynak"] == k for s in sec])
        if m.any():
            sinif[m] = arazi.sinif(lon[m], lat[m], r)
    disari = 0
    with open(CIKTI + ".tmp", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, ALANLAR); w.writeheader()
        for r, i, c, s in zip(sec, il, ilce, sinif):
            if i is None:
                disari += 1; continue
            w.writerow({"kaynak": r["kaynak"], "tarih": r["tarih"], "saat": r["saat"], "lat": r["lat"], "lon": r["lon"],
                        "frp": r["frp"], "gece": int(r["gece"]), "il": i, "ilce": c or "", "sinif": s})
    os.replace(CIKTI + ".tmp", CIKTI)
    bilgi.update({"secilen": len(sec), "turkiye_disi": disari, "yazilan": len(sec) - disari})
    print(bilgi)
    return bilgi


def oku():
    with open(CIKTI, encoding="utf8") as f:
        return [{**r, "lat": float(r["lat"]), "lon": float(r["lon"]), "frp": float(r["frp"])} for r in csv.DictReader(f)]


if __name__ == "__main__":
    import json
    b = isle()
    json.dump(b, open("veri/tespit_bilgi.json", "w"), indent=1)
