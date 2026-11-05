import numpy as np
from shapely.geometry import box

import firms
import olaylar
from konum import Bolgeler


def bolgeler():
    # iki bitişik "il": A (0–1°), B (1–2°), boylam ekseninde
    return Bolgeler(["A", "B"], [box(0, 0, 1, 1), box(1, 0, 2, 1)])


def test_icindeki_nokta_dogru_ile():
    r = bolgeler().ata([0.5, 1.5], [0.5, 0.5])
    assert list(r) == ["A", "B"]


def test_kiyiya_yakin_nokta_en_yakin_ile():
    # sınırın 0,01° (~1,1 km) dışında: 3 km eşiğinin içinde -> en yakın il
    r = bolgeler().ata([-0.01], [0.5])
    assert list(r) == ["A"]


def test_uzaktaki_nokta_atilir():
    # ~11 km dışarıda (deniz / komşu ülke)
    r = bolgeler().ata([-0.1], [0.5])
    assert r[0] is None


def test_bos_girdi():
    assert len(bolgeler().ata([], [])) == 0


def test_gercek_iller_bilinen_noktalar():
    import os, pytest
    yol = "veri/ham/tur_adm1.geojson"
    if not os.path.exists(yol):
        pytest.skip("il sınırları indirilmemiş (python indir.py)")
    b = Bolgeler.dosyadan(yol)
    # Manavgat merkezi, Marmaris merkezi, Ankara Kızılay, Şanlıurfa merkezi
    r = b.ata([31.443, 28.274, 32.854, 38.794], [36.787, 36.855, 39.920, 37.159])
    assert list(r) == ["Antalya", "Muğla", "Ankara", "Şanlıurfa"]


def test_sabit_kaynak_suzulur():
    arsiv = [{"kaynak": "V", "lat": 40.0, "lon": 30.0, "tip": 2, "guven": "n"}]
    sabit = firms.sabit_hucreler(arsiv)
    nrt_ayni = {"kaynak": "V", "lat": 40.003, "lon": 30.004, "tip": -1, "guven": "n"}
    nrt_uzak = {"kaynak": "V", "lat": 40.2, "lon": 30.2, "tip": -1, "guven": "n"}
    dusuk = {"kaynak": "V", "lat": 40.2, "lon": 30.2, "tip": 0, "guven": "l"}
    assert firms.suz([nrt_ayni, nrt_uzak, dusuk] + arsiv, sabit) == [nrt_uzak]


def test_kumeleme_yer_ve_zaman():
    n = [{"lat": 37.0, "lon": 31.0, "tarih": "2021-07-28"},
         {"lat": 37.01, "lon": 31.0, "tarih": "2021-07-29"},   # ~1,1 km, 1 gün: aynı yangın
         {"lat": 37.02, "lon": 31.0, "tarih": "2021-07-30"},   # zincirle bağlı
         {"lat": 37.0, "lon": 31.0, "tarih": "2021-08-20"},    # aynı yer, çok sonra: ayrı
         {"lat": 37.2, "lon": 31.0, "tarih": "2021-07-28"}]    # ~22 km: ayrı
    e = olaylar.kumele(n)
    assert e[0] == e[1] == e[2]
    assert len({e[0], e[3], e[4]}) == 3
