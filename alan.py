"""Yanmış alan hesabı (saf numpy; ağ yok, test edilebilir).

Yöntem
- NBR (Normalleştirilmiş Yanma Oranı) = (YKÖ − KDKÖ) / (YKÖ + KDKÖ)
  Sentinel-2: YKÖ = B8A (865 nm), KDKÖ = B12 (2190 nm), ikisi de 20 m.
- dNBR = NBR(önce) − NBR(sonra). Yanan bitki örtüsünde NBR düşer, dNBR artar.
- Eşikler Key & Benson (2006, FIREMON) sınıflarından:
    ≥ 0,10 düşük şiddet ve üstü   (geniş tahmin)
    ≥ 0,27 orta-düşük ve üstü     (ANA ESİK: sitede verilen sayı)
    ≥ 0,44 orta-yüksek ve üstü
    ≥ 0,66 yüksek şiddet
- Yalnız iki görüntüde de açıkça görünen pikseller sayılır. Önceki görüntüde bulut, bulut
  gölgesi, su, kar ve bozuk pikseller; sonraki görüntüde yalnız bulut, kar ve bozuk pikseller
  atılır. (Sen2Cor sınıflandırması taze yanık izini sık sık "bulut gölgesi" ya da "su" sanır;
  sonraki görüntüde bunları atmak yanığın kendisini silerdi.) Görünmeyen pikseller alana
  EKLENMEZ: verilen sayı alt sınırdır.
- Yalnız FIRMS tespitlerinin çevresindeki "arama alanı" içi sayılır; böylece hasat edilmiş
  tarlalar gibi yangınla ilgisiz değişimler büyük ölçüde dışarıda kalır.
- Piksel 20 m × 20 m = 400 m² = 0,04 ha.
"""
import numpy as np

ESIKLER = {"genis": 0.10, "ana": 0.27, "orta_yuksek": 0.44, "yuksek": 0.66}
ANA_ESIK = ESIKLER["ana"]
PIKSEL_M2 = 400.0
# SCL: 0 boş, 1 doymuş/bozuk, 3 bulut gölgesi, 6 su, 8-9 bulut, 10 ince sirrus, 11 kar
ONCE_GORUNMEZ = (0, 1, 3, 6, 8, 9, 10, 11)
SONRA_GORUNMEZ = (0, 1, 8, 9, 10, 11)


def nbr(nir, swir):
    nir = np.asarray(nir, "float32"); swir = np.asarray(swir, "float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        n = (nir - swir) / (nir + swir)
    n[~np.isfinite(n)] = np.nan
    return n


def ndvi(nir, kirmizi):
    return nbr(nir, kirmizi)  # aynı biçim: (a − b) / (a + b)


def gorunur(scl, *bantlar, gorunmez=ONCE_GORUNMEZ):
    """SCL'ye ve bant değerlerine göre kullanılabilir pikseller."""
    m = ~np.isin(np.asarray(scl), gorunmez)
    for b in bantlar:
        b = np.asarray(b, "float32")
        m &= np.isfinite(b) & (b > 0)
    return m


def dnbr(once_nbr, sonra_nbr):
    return np.asarray(once_nbr, "float32") - np.asarray(sonra_nbr, "float32")


def yanan_alan(d, gecerli, arama, esik=ANA_ESIK, piksel_m2=PIKSEL_M2):
    """d: dNBR dizisi. gecerli: iki görüntüde de görünen pikseller. arama: arama alanı maskesi.

    Dönüş: dict(ha, piksel, arama_piksel, gorunmez_oran)
    """
    d = np.asarray(d, "float32")
    arama = np.asarray(arama, bool)
    gecerli = np.asarray(gecerli, bool) & np.isfinite(d)
    n_arama = int(arama.sum())
    if n_arama == 0:
        raise ValueError("arama alanı boş")
    say = arama & gecerli
    yanik = say & (d >= esik)
    n = int(yanik.sum())
    return {"ha": n * piksel_m2 / 1e4, "piksel": n, "arama_piksel": n_arama,
            "gorunmez_oran": 1 - int(say.sum()) / n_arama}


def tum_esikler(d, gecerli, arama):
    return {ad: yanan_alan(d, gecerli, arama, esik=e)["ha"] for ad, e in ESIKLER.items()}


def toparla(yanik, en_az_piksel=5):
    """Tek başına kalmış küçük yanık kümelerini (gürültü) atar: 8-komşulukta en_az_piksel'den
    küçük bağlı bileşenler silinir."""
    from scipy import ndimage
    yanik = np.asarray(yanik, bool)
    etiket, n = ndimage.label(yanik, structure=np.ones((3, 3), bool))
    if n == 0:
        return yanik.copy()
    boy = np.bincount(etiket.ravel())
    tut = boy >= en_az_piksel
    tut[0] = False
    return tut[etiket]
