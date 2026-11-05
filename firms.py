"""NASA FIRMS etkin yangın tespitlerini okur ve süzer.

Arşiv (ülke yıllık dosyaları) her tespite bir "type" verir:
  0 bitki yangını olduğu varsayılan, 1 etkin yanardağ, 2 diğer sabit kara kaynağı
  (fabrika bacası, rafineri, gaz alevi...), 3 deniz üstü.
Biz yalnız 0'ı tutarız. Yakın zaman (NRT) dosyalarında bu alan yok; onlarda arşivde
"sabit kaynak" diye işaretlenmiş hücrelere düşen tespitler atılır.

Güven düzeyi: VIIRS 'l' (düşük) ve MODIS < GUVEN_MODIS olanlar atılır.
"""
import csv, glob, os
import numpy as np

GUVEN_MODIS = 30
SABIT_HUCRE = 0.01   # derece; sabit kaynak hücresi (~1 km)

ALANLAR = ["kaynak", "tarih", "saat", "lat", "lon", "frp", "guven", "gece", "tip"]


def satir_oku(yol, kaynak):
    """FIRMS CSV'sini ortak biçime çevirir. kaynak: 'M' (MODIS) ya da 'V' (VIIRS)."""
    cikti = []
    with open(yol, encoding="utf8") as f:
        for r in csv.DictReader(f):
            cikti.append({
                "kaynak": kaynak,
                "tarih": r["acq_date"],
                "saat": r["acq_time"].zfill(4),
                "lat": float(r["latitude"]),
                "lon": float(r["longitude"]),
                "frp": float(r["frp"] or 0),
                "guven": r["confidence"],
                "gece": r.get("daynight", "D") == "N",
                "tip": int(r["type"]) if r.get("type", "") not in ("", None) else -1,
            })
    return cikti


def guvenilir(r):
    g = r["guven"]
    if r["kaynak"] == "V":
        return g not in ("l", "low")
    try:
        return int(g) >= GUVEN_MODIS
    except ValueError:
        return True


def hucre(lon, lat, adim=SABIT_HUCRE):
    return (int(np.floor(lon / adim)), int(np.floor(lat / adim)))


def sabit_hucreler(satirlar):
    """Arşivde type=2 olan tespitlerin düştüğü hücreler ve komşuları."""
    s = set()
    for r in satirlar:
        if r["tip"] == 2:
            x, y = hucre(r["lon"], r["lat"])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    s.add((x + dx, y + dy))
    return s


def suz(satirlar, sabit):
    """Bitki yangını olabilecek, güvenilir tespitleri döndürür."""
    out = []
    for r in satirlar:
        if not guvenilir(r):
            continue
        if r["tip"] in (1, 2, 3):
            continue
        if r["tip"] == -1 and hucre(r["lon"], r["lat"]) in sabit:
            continue
        out.append(r)
    return out


def arsiv_oku(ham="veri/ham"):
    satir = []
    for yol in sorted(glob.glob(os.path.join(ham, "modis_*.csv"))):
        satir += satir_oku(yol, "M")
    for yol in sorted(glob.glob(os.path.join(ham, "viirs-snpp_*.csv"))):
        satir += satir_oku(yol, "V")
    return satir


def tekille(satirlar):
    """Aynı kaynak/tarih/saat/konumdaki kopyaları atar (NRT dosyaları üst üste biner)."""
    gor = set(); out = []
    for r in satirlar:
        k = (r["kaynak"], r["tarih"], r["saat"], round(r["lat"], 4), round(r["lon"], 4))
        if k not in gor:
            gor.add(k); out.append(r)
    return out
