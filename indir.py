"""Ham verileri indirir (anahtar gerekmez).

- NASA FIRMS ülke yıllık arşivleri (Türkiye): MODIS 2001+, VIIRS S-NPP 2012+.
  https://firms.modaps.eosdis.nasa.gov/country/
- geoBoundaries il (ADM1) ve ilçe (ADM2) sınırları (OpenStreetMap kaynaklı).

Kullanım: python indir.py [--yil-son 2025]
Var olan dosyalar yeniden indirilmez.
"""
import argparse, datetime as dt, os, sys, time
import requests

HAM = "veri/ham"
FIRMS = "https://firms.modaps.eosdis.nasa.gov/data/country/{k}/{y}/{k}_{y}_Turkey.csv"
KAYNAKLAR = {"modis": 2001, "viirs-snpp": 2012}
GB = "https://www.geoboundaries.org/api/current/gbOpen/TUR/{d}/"


def getir(url, yol):
    if os.path.exists(yol) and os.path.getsize(yol) > 0:
        return False
    for deneme in range(5):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            tmp = yol + ".tmp"
            with open(tmp, "wb") as f:
                f.write(r.content)
            os.replace(tmp, yol)
            return True
        except requests.RequestException as e:
            print("hata, yeniden:", url, e, file=sys.stderr)
            time.sleep(5 * (deneme + 1))
    raise SystemExit("indirilemedi: " + url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yil-son", type=int, default=dt.date.today().year - 1)
    a = ap.parse_args()
    os.makedirs(HAM, exist_ok=True)
    for k, bas in KAYNAKLAR.items():
        for y in range(bas, a.yil_son + 1):
            s = getir(FIRMS.format(k=k, y=y), f"{HAM}/{k}_{y}.csv")
            print(k, y, {True: "indi", False: "var", None: "yok (404)"}[s], flush=True)
    for d in ("ADM1", "ADM2"):
        yol = f"{HAM}/tur_{d.lower()}.geojson"
        if not os.path.exists(yol):
            meta = requests.get(GB.format(d=d), timeout=60).json()
            getir(meta["simplifiedGeometryGeoJSON"], yol)
            print(d, "indi")


if __name__ == "__main__":
    main()
