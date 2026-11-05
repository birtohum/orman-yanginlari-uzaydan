"""Yıllık arşivde henüz olmayan (bu yılki) tespitleri toplar -> veri/nrt.csv

1) Anahtarsız: FIRMS'in herkese açık "son 7 gün" bölge dosyaları (Avrupa + Rusya/Asya;
   Türkiye ikisinin sınırında). Her gün çalıştırılırsa kayıp olmadan birikir.
2) FIRMS_MAP_KEY varsa (ortam değişkeni ya da .env): yılbaşından bugüne boşlukları
   FIRMS API'nin alan uç noktasıyla 5 günlük parçalar halinde doldurur.

Anahtar ücretsizdir: https://firms.modaps.eosdis.nasa.gov/api/map_key/
"""
import csv, datetime as dt, io, json, os, sys, time
import requests

from firms import ALANLAR, tekille

NRT = "veri/nrt.csv"
PARCALAR = "veri/nrt_parcalar.json"
ACIK = {
    "V": ["https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Europe_7d.csv",
          "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Russia_Asia_7d.csv"],
    "M": ["https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Europe_7d.csv",
          "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Russia_Asia_7d.csv"],
}
# Ülke uç noktası (country/…/TUR) 2026 sonbaharında "Invalid API call" vermeye başladı; alan uç noktası en fazla 5 gün alıyor.
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/25.5,35.75,45,42.25/{gun}/{tarih}"
PARCA_GUN = 5
API_KAYNAK = {"V": ["VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"], "M": ["MODIS_SP", "MODIS_NRT"]}
# Türkiye'yi kapsayan kutu; komşu ülke noktaları sonra il atamasında elenir
KUTU = (25.5, 35.75, 45.0, 42.25)


def anahtar():
    k = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not k and os.path.exists(".env"):
        for satir in open(".env", encoding="utf8"):
            if satir.strip().startswith("FIRMS_MAP_KEY="):
                k = satir.split("=", 1)[1].strip().strip('"').strip("'")
    return k or None


def cevir(metin, kaynak):
    out = []
    for r in csv.DictReader(io.StringIO(metin)):
        try:
            lat = float(r["latitude"]); lon = float(r["longitude"])
        except (KeyError, ValueError):
            continue
        if not (KUTU[0] <= lon <= KUTU[2] and KUTU[1] <= lat <= KUTU[3]):
            continue
        t = r.get("type", "")
        out.append({"kaynak": kaynak, "tarih": r["acq_date"], "saat": r["acq_time"].zfill(4), "lat": lat, "lon": lon,
                    "frp": float(r.get("frp") or 0), "guven": r["confidence"], "gece": r.get("daynight") == "N",
                    "tip": int(t) if t not in ("", None) else -1})
    return out


def getir(url):
    for deneme in range(4):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200:
                return r.text
            print("FIRMS", r.status_code, url.split("/api/")[-1][:20] if "/api/" in url else url, file=sys.stderr)
        except requests.RequestException as e:
            print("FIRMS hata:", e, file=sys.stderr)
        time.sleep(5 * (deneme + 1))
    return None


def oku():
    if not os.path.exists(NRT):
        return []
    with open(NRT, encoding="utf8") as f:
        return [{**r, "lat": float(r["lat"]), "lon": float(r["lon"]), "frp": float(r["frp"]),
                 "gece": r["gece"] == "1", "tip": int(r["tip"])} for r in csv.DictReader(f)]


def yaz(satirlar):
    satirlar = sorted(tekille(satirlar), key=lambda r: (r["tarih"], r["saat"], r["kaynak"], r["lat"], r["lon"]))
    with open(NRT + ".tmp", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, ALANLAR); w.writeheader()
        for r in satirlar:
            w.writerow({**r, "gece": int(r["gece"])})
    os.replace(NRT + ".tmp", NRT)
    return len(satirlar)


def main():
    yil = dt.date.today().year
    bas_yil = f"{yil}-01-01"
    satir = [r for r in oku() if r["tarih"] >= bas_yil]
    yeni = []
    for k, urller in ACIK.items():
        for u in urller:
            m = getir(u)
            if m:
                yeni += cevir(m, k)
    print("açık 7 günlük dosyalardan", len(yeni), "satır")
    key = anahtar()
    parca = json.load(open(PARCALAR)) if os.path.exists(PARCALAR) else {}
    if key:
        bugun = dt.date.today()
        b = dt.date(yil, 1, 1)
        while b <= bugun:
            son = min(bugun, b + dt.timedelta(days=PARCA_GUN - 1))
            gun = (son - b).days + 1
            for k, kaynaklar in API_KAYNAK.items():
                ad = f"{k}:{b.isoformat()}"
                # tamamlanmış parça (bugünden en az 10 gün önce bitmiş) tekrar çekilmez
                if parca.get(ad) == "tamam":
                    continue
                cevap_geldi = False
                for src in kaynaklar:
                    m = getir(API.format(key=key, src=src, gun=gun, tarih=b.isoformat()))
                    cevap_geldi = cevap_geldi or m is not None
                    s = cevir(m, k) if m else []
                    if s:
                        yeni += s
                        break
                # yalnız gerçekten cevap alınan ve bugünden en az 10 gün önce bitmiş parça kapanır
                if cevap_geldi and (bugun - son).days >= 10:
                    parca[ad] = "tamam"
            b = son + dt.timedelta(days=1)
        json.dump(parca, open(PARCALAR, "w"), indent=0, sort_keys=True)
    else:
        print("FIRMS_MAP_KEY yok: yalnız son 7 gün eklendi. Yılbaşından bugüne boşluk için anahtar gerekli.")
    n = yaz(satir + [r for r in yeni if r["tarih"] >= bas_yil])
    print("veri/nrt.csv:", n, "satır")


if __name__ == "__main__":
    main()
