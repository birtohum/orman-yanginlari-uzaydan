import numpy as np
import pytest

import alan


def test_nbr_bilinen_deger():
    # (0,4 − 0,1) / (0,4 + 0,1) = 0,6
    assert alan.nbr(np.array([0.4]), np.array([0.1]))[0] == pytest.approx(0.6)


def test_nbr_sifir_bolme_nan():
    assert np.isnan(alan.nbr(np.array([0.0]), np.array([0.0]))[0])


def test_dnbr_yanikta_pozitif():
    once = alan.nbr(np.array([0.35]), np.array([0.10]))   # sağlıklı orman
    sonra = alan.nbr(np.array([0.15]), np.array([0.25]))  # yanık
    assert alan.dnbr(once, sonra)[0] > alan.ESIKLER["yuksek"]


def test_alan_piksel_basina_004_ha():
    d = np.zeros((10, 10), np.float32); d[:5, :4] = 0.5     # 20 yanık piksel
    tam = np.ones((10, 10), bool)
    r = alan.yanan_alan(d, tam, tam)
    assert r["piksel"] == 20
    assert r["ha"] == pytest.approx(20 * 0.04)               # 20 m × 20 m = 0,04 ha
    assert r["gorunmez_oran"] == 0


def test_esik_dahil_ve_alti_haric():
    d = np.array([[0.27, 0.2699, 0.44, 0.1]], np.float32)
    tam = np.ones_like(d, bool)
    assert alan.yanan_alan(d, tam, tam)["piksel"] == 2       # 0,27 dahil, 0,2699 hariç
    assert alan.yanan_alan(d, tam, tam, esik=0.10)["piksel"] == 4
    e = alan.tum_esikler(d, tam, tam)
    assert e["genis"] >= e["ana"] >= e["orta_yuksek"] >= e["yuksek"]


def test_arama_disi_ve_gorunmez_sayilmaz():
    d = np.full((4, 4), 0.6, np.float32)
    arama = np.zeros((4, 4), bool); arama[:2] = True         # 8 piksel
    gecerli = np.ones((4, 4), bool); gecerli[0, :2] = False  # 2'si bulutlu
    r = alan.yanan_alan(d, gecerli, arama)
    assert r["piksel"] == 6
    assert r["gorunmez_oran"] == pytest.approx(2 / 8)


def test_nan_dnbr_sayilmaz():
    d = np.array([[np.nan, 0.5]], np.float32)
    tam = np.ones_like(d, bool)
    assert alan.yanan_alan(d, tam, tam)["piksel"] == 1


def test_bos_arama_hata():
    with pytest.raises(ValueError):
        alan.yanan_alan(np.zeros((2, 2)), np.ones((2, 2), bool), np.zeros((2, 2), bool))


def test_gorunur_once_su_atilir_sonra_tutulur():
    scl = np.array([[6, 3, 4, 9]])
    b = np.ones((1, 4))
    assert alan.gorunur(scl, b, gorunmez=alan.ONCE_GORUNMEZ).tolist() == [[False, False, True, False]]
    # sonraki görüntüde yanık izi "su" ya da "gölge" sanılabilir: atılmaz, bulut atılır
    assert alan.gorunur(scl, b, gorunmez=alan.SONRA_GORUNMEZ).tolist() == [[True, True, True, False]]


def test_toparla_kucuk_kumeleri_siler():
    m = np.zeros((10, 10), bool)
    m[0, 0] = True                 # tek piksel: gürültü
    m[5:8, 5:8] = True             # 9 piksel: kalır
    t = alan.toparla(m, en_az_piksel=5)
    assert not t[0, 0] and t[5:8, 5:8].all() and t.sum() == 9
