"""Bir noktanın hangi ilde/ilçede olduğu ve arazi örtüsü.

İl/ilçe: geoBoundaries (OpenStreetMap) sınırları, sadeleştirilmiş. Sadeleştirme kıyıda
küçük boşluklar bıraktığı için sınır dışında kalan nokta, en yakın ile ENYAKIN_KM'den
yakınsa o ile verilir; daha uzaksa (deniz, komşu ülke) atılır.

Arazi örtüsü: ESA WorldCover 2020 (10 m), Türkiye için ~150 m'lik genel görünümünden
okunur ve dört sınıfa indirgenir (bkz. SINIF).
"""
import json, math, os
import numpy as np
from shapely import STRtree, points as sh_points
from shapely.geometry import shape

ENYAKIN_KM = 3.0

# --- il / ilçe -------------------------------------------------------------------------


class Bolgeler:
    """Poligon listesi üzerinde hızlı nokta→bölge ataması."""

    def __init__(self, adlar, geometriler):
        self.adlar = list(adlar)
        self.geom = list(geometriler)
        self.agac = STRtree(self.geom)

    @classmethod
    def dosyadan(cls, yol):
        fc = json.load(open(yol, encoding="utf8"))
        return cls([f["properties"]["shapeName"] for f in fc["features"]],
                   [shape(f["geometry"]).buffer(0) for f in fc["features"]])

    def ata(self, lon, lat, enyakin_km=ENYAKIN_KM):
        """lon, lat dizileri -> bölge adı dizisi (bulunamayan: None)."""
        lon = np.asarray(lon, float); lat = np.asarray(lat, float)
        sonuc = np.full(len(lon), None, dtype=object)
        if len(lon) == 0:
            return sonuc
        p = sh_points(np.column_stack([lon, lat]))
        nokta_i, poligon_i = self.agac.query(p, predicate="intersects")
        # bir nokta iki poligonun ortak sınırındaysa ilk bulunan alınır
        gorulen = np.zeros(len(lon), bool)
        for ni, pi in zip(nokta_i, poligon_i):
            if not gorulen[ni]:
                sonuc[ni] = self.adlar[pi]; gorulen[ni] = True
        kalan = np.where(~gorulen)[0]
        if len(kalan):
            # derece cinsinden yaklaşık eşik (enlemde 1° ≈ 111 km; boylamda biraz daha az: güvenli taraf)
            esik = enyakin_km / 111.0
            yi, pi = self.agac.query_nearest(p[kalan], max_distance=esik, return_distance=False, all_matches=False)
            for a, b in zip(yi, pi):
                sonuc[kalan[a]] = self.adlar[b]
        return sonuc


# --- arazi örtüsü ---------------------------------------------------------------------

# Türkiye'yi kapsayan ızgara (derece)
BATI, DOGU, GUNEY, KUZEY = 25.5, 45.0, 35.75, 42.25
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map/ESA_WorldCover_10m_2020_v100_{ns}{lat:02d}{ew}{lon:03d}_Map.tif"
WC_OLCEK = 16          # 10 m'lik karonun 1/16'sı: ~0,00133° ≈ 150 m
WC_ADIM = 3 / 36000 * WC_OLCEK

# ESA WorldCover sınıfı -> bizim sınıfımız
#   1 orman ve makilik (10 ağaç örtüsü, 20 çalılık)
#   2 tarım (40 ekili alan)
#   3 diğer bitki örtüsü (30 çayır, 90 sulak alan, 100 yosun/liken)
#   0 bitki dışı (50 yapı, 60 çıplak, 70 kar, 80 su, 0 veri yok)
SINIF = {10: 1, 20: 1, 40: 2, 30: 3, 90: 3, 95: 3, 100: 3}
SINIF_AD = {1: "orman", 2: "tarim", 3: "diger", 0: "diger"}


def worldcover_indir(cikti="veri/arazi.png"):
    """WorldCover karolarını genel görünümden okuyup 4 sınıflı tek bir PNG yazar."""
    import rasterio
    from PIL import Image
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    gen = int(round((DOGU - BATI) / WC_ADIM)); yuk = int(round((KUZEY - GUNEY) / WC_ADIM))
    tum = np.zeros((yuk, gen), np.uint8)
    lut = np.zeros(256, np.uint8)
    for k, v in SINIF.items():
        lut[k] = v
    for la in range(33, 43, 3):
        for lo in range(24, 45, 3):
            url = WC_URL.format(ns="N", lat=la, ew="E", lon=lo)
            try:
                with rasterio.open(url) as s:
                    n = s.width // WC_OLCEK
                    a = s.read(1, out_shape=(n, n))
            except Exception:
                continue  # denizdeki karolar yok
            a = lut[a]
            # karonun sol üst köşesi (lo, la+3)
            x0 = int(round((lo - BATI) / WC_ADIM)); y0 = int(round((KUZEY - (la + 3)) / WC_ADIM))
            xs0, ys0 = max(0, -x0), max(0, -y0)
            xd0, yd0 = max(0, x0), max(0, y0)
            w = min(n - xs0, gen - xd0); h = min(n - ys0, yuk - yd0)
            if w > 0 and h > 0:
                tum[yd0:yd0 + h, xd0:xd0 + w] = a[ys0:ys0 + h, xs0:xs0 + w]
            print("WorldCover", la, lo, flush=True)
    Image.fromarray(tum, "L").save(cikti, optimize=True)
    return cikti


class Arazi:
    def __init__(self, yol="veri/arazi.png"):
        from PIL import Image
        self.a = np.asarray(Image.open(yol))

    def orman_payi(self, lon, lat, yaricap_m):
        """Her noktanın çevresindeki (kare, yarı kenar ≈ yaricap_m) orman+makilik oranı."""
        lon = np.asarray(lon, float); lat = np.asarray(lat, float)
        r = max(1, int(round(yaricap_m / 150)))
        x = np.round((lon - BATI) / WC_ADIM).astype(int)
        y = np.round((KUZEY - lat) / WC_ADIM).astype(int)
        H, W = self.a.shape
        orman = np.zeros(len(x)); tarim = np.zeros(len(x)); n = np.zeros(len(x))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                yy = np.clip(y + dy, 0, H - 1); xx = np.clip(x + dx, 0, W - 1)
                s = self.a[yy, xx]
                orman += s == 1; tarim += s == 2; n += 1
        return orman / n, tarim / n

    def sinif(self, lon, lat, yaricap_m):
        """'orman' (orman+makilik payı ≥ %50), 'tarim' (tarım payı ≥ %50) ya da 'diger'."""
        o, t = self.orman_payi(lon, lat, yaricap_m)
        return np.where(o >= 0.5, "orman", np.where(t >= 0.5, "tarim", "diger"))


def mesafe_km(lon1, lat1, lon2, lat2):
    """Küçük mesafeler için eşdikdörtgen yaklaşım (km)."""
    x = (np.asarray(lon2) - lon1) * math.cos(math.radians((lat1 + np.asarray(lat2)) / 2))
    y = np.asarray(lat2) - lat1
    return 111.32 * np.hypot(x, y)
