"""Büyük yangınlar için Sentinel-2 L2A'dan önce/sonra görüntüsü, dNBR yanık alanı ve
yıllara göre yeşillenme (NDVI) eğrisi.

Kaynak: Element84 Earth Search STAC (AWS açık veri, hesap gerekmez). Yalnız yangının
çevresindeki pencere okunur (COG aralık istekleri), tüm karo indirilmez.

Kullanım: python uydu.py [--adet 12] [--id OLAY_ID]
Girdi:  veri/olay_adaylari.json  (uret.py yazar)
Çıktı:  veri/olaylar.json, site/gorsel/<id>_{once,sonra}.jpg, <id>_yanik.png
"""
import argparse, datetime as dt, json, math, os, sys, time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")

import numpy as np
import rasterio
import requests
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from shapely.geometry import MultiPoint, box
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from shapely.ops import transform as sh_transform

import alan

STAC = "https://earth-search.aws.element84.com/v1/search"
KOLEKSIYON = "sentinel-2-l2a"
RES = 20
ARAMA_M = 1000      # FIRMS tespitlerinin çevresinde aranacak mesafe
KENAR_M = 2500      # görüntü çerçevesi için ek pay
ONCE_GUN = 75
SONRA_GUN = (3, 75)
GORSEL_EN = 960


def utm_crs(lon, lat):
    return f"EPSG:{(32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1}"


def izgara(kutu, crs, res=RES, kenar=KENAR_M):
    tr = Transformer.from_crs(4326, crs, always_xy=True)
    g = sh_transform(tr.transform, box(*kutu)).buffer(kenar)
    x0, y0, x1, y1 = g.bounds
    x0 = math.floor(x0 / 60) * 60; y0 = math.floor(y0 / 60) * 60
    x1 = math.ceil(x1 / 60) * 60; y1 = math.ceil(y1 / 60) * 60
    w = int((x1 - x0) / res); h = int((y1 - y0) / res)
    return from_origin(x0, y1, res, res), w, h


def ara(kutu, bas, son, bulut=80):
    govde = {"collections": [KOLEKSIYON], "bbox": list(kutu),
             "datetime": f"{bas}T00:00:00Z/{son}T23:59:59Z", "limit": 200,
             "query": {"eo:cloud_cover": {"lte": bulut}}}
    ogeler = []
    while True:
        for deneme in range(8):
            try:
                r = requests.post(STAC, json=govde, timeout=120); r.raise_for_status(); break
            except Exception as e:
                print("STAC hata, yeniden:", e, file=sys.stderr); time.sleep(5 * (deneme + 1))
        else:
            raise SystemExit("STAC yanıt vermiyor")
        d = r.json(); ogeler += d["features"]
        sonraki = [l for l in d.get("links", []) if l["rel"] == "next"]
        if not sonraki or not d["features"]:
            break
        govde = sonraki[0].get("body", govde)
    # gün -> karo -> en yüksek sıra numaralı öğe
    gun = {}
    for f in ogeler:
        t = f["properties"]["datetime"][:10]
        k = f["properties"].get("grid:code", f["id"])
        n = int(f["properties"].get("s2:sequence", 0) or 0)
        if (t, k) not in gun or n > gun[(t, k)][0]:
            gun[(t, k)] = (n, f)
    sonuc = {}
    for (t, k), (n, f) in gun.items():
        sonuc.setdefault(t, []).append(f)
    return dict(sorted(sonuc.items()))


def bant(oge, ad):
    """Bandın adresi, ölçeği, ötelemesi. Ötelemenin mantığı için barajlar/cek.py'ye bkz.:
    Earth Search ESA'nın +1000 kaydırmasını zaten geri aldıysa (boa_offset_applied) tekrar uygulanmaz."""
    a = oge["assets"][ad]
    if ad in ("scl", "visual"):
        return a["href"], 1, 0.0
    p = oge["properties"]
    surum = float(p.get("s2:processing_baseline", "0") or 0)
    oteleme = 0.0 if (p.get("earthsearch:boa_offset_applied") or surum < 4.0) else -0.1
    return a["href"], 1e-4, oteleme


def oku(ogeler, ad, crs, transform, w, h, ornek=Resampling.nearest):
    """Aynı güne ait karoları hedef ızgaraya çevirip birleştirir. Boş: NaN (scl/visual için 0)."""
    gorsel = ad == "visual"
    out = np.zeros((3, h, w), np.uint8) if gorsel else np.full((h, w), np.nan, np.float32)
    for o in ogeler:
        href, olcek, ot = bant(o, ad)
        if not href.endswith(".tif"):
            continue  # bazı eski kayıtlarda yalnız ücretli S3'teki JP2 var
        with rasterio.open(href) as src, WarpedVRT(src, crs=crs, transform=transform, width=w, height=h,
                                                   resampling=ornek, src_nodata=0, nodata=0) as v:
            a = v.read() if gorsel else v.read(1)
        if gorsel:
            bos = out.sum(0) == 0
            dolu = a.sum(0) > 0
            m = bos & dolu
            out[:, m] = a[:, m]
        else:
            m = np.isnan(out) & (a != 0)
            out[m] = a[m].astype(np.float32) * olcek + ot if ad != "scl" else a[m]
    return out


def gecerlilik(ogeler, crs, transform, w, h, arama, gorunmez):
    scl = oku(ogeler, "scl", crs, transform, w, h)
    s = np.nan_to_num(scl, nan=0).astype(np.uint8)
    g = ~np.isin(s, gorunmez)
    return float((g & arama).sum() / max(1, arama.sum())), s


def sec(gunler, crs, transform, w, h, arama, gorunmez, ilk_yeterli=None, yakin=None):
    """En çok görünen günü seçer. ilk_yeterli verilirse o orana ulaşan ilk gün alınır.
    yakin verilirse eşitlikte o tarihe yakın olan tercih edilir."""
    aday = []
    for t, og in gunler.items():
        try:
            oran, scl = gecerlilik(og, crs, transform, w, h, arama, gorunmez)
        except Exception as e:
            print("  okunamadı", t, str(e)[:120], file=sys.stderr); continue
        aday.append((t, oran, og, scl))
        if ilk_yeterli is not None and oran >= ilk_yeterli:
            return aday[-1]
    if not aday:
        return None
    if yakin:
        yk = dt.date.fromisoformat(yakin).toordinal()
        return max(aday, key=lambda a: (round(a[1], 2), -abs(dt.date.fromisoformat(a[0]).toordinal() - yk)))
    return max(aday, key=lambda a: a[1])


def jpg(rgb, yol):
    Image.fromarray(np.transpose(rgb, (1, 2, 0))).save(yol, quality=82, optimize=True, progressive=True)


def kucult_maske(m, k):
    """k×k bloklarda en az yarısı yanık olan blok yanık sayılır."""
    H, W = m.shape
    h, w = math.ceil(H / k), math.ceil(W / k)
    p = np.zeros((h * k, w * k), bool); p[:H, :W] = m
    return p.reshape(h, k, w, k).mean((1, 3)) >= 0.5


def olc(olay, gorsel_dizin="site/gorsel"):
    kutu = olay["kutu"]
    cx, cy = (kutu[0] + kutu[2]) / 2, (kutu[1] + kutu[3]) / 2
    crs = utm_crs(cx, cy)
    transform, w, h = izgara(kutu, crs)
    tr = Transformer.from_crs(4326, crs, always_xy=True)
    nokta = sh_transform(tr.transform, MultiPoint(olay["noktalar"]))
    arama_g = nokta.buffer(ARAMA_M)
    arama = ~geometry_mask([arama_g], out_shape=(h, w), transform=transform)
    lonlat_kutu = list(kutu)
    bas = dt.date.fromisoformat(olay["bas"]); son = dt.date.fromisoformat(olay["son"])
    # arama kutusu (derece) biraz genişletilmiş
    ak = [kutu[0] - 0.03, kutu[1] - 0.03, kutu[2] + 0.03, kutu[3] + 0.03]

    once_gun = ara(ak, (bas - dt.timedelta(days=ONCE_GUN)).isoformat(), (bas - dt.timedelta(days=1)).isoformat())
    once_gun = dict(sorted(once_gun.items(), reverse=True))  # yangına yakın olandan başla
    # seçimde yalnız bulut sayılır (kıyıdaki deniz pikselleri görüntüyü "kötü" göstermesin)
    o = sec(once_gun, crs, transform, w, h, arama, alan.SONRA_GORUNMEZ, ilk_yeterli=0.98)
    sonra_gun = ara(ak, (son + dt.timedelta(days=SONRA_GUN[0])).isoformat(), (son + dt.timedelta(days=SONRA_GUN[1])).isoformat())
    s = sec(sonra_gun, crs, transform, w, h, arama, alan.SONRA_GORUNMEZ, ilk_yeterli=0.95)
    if not o or not s:
        print("  uygun görüntü yok", olay["id"]); return None
    ot, oo, og, oscl = o; st, so, sg, sscl = s
    print(f"  önce {ot} (%{oo*100:.0f} görünür), sonra {st} (%{so*100:.0f})", flush=True)

    on_nir = oku(og, "nir08", crs, transform, w, h); on_sw = oku(og, "swir22", crs, transform, w, h)
    so_nir = oku(sg, "nir08", crs, transform, w, h); so_sw = oku(sg, "swir22", crs, transform, w, h)
    gecerli = (alan.gorunur(oscl, on_nir, on_sw, gorunmez=alan.ONCE_GORUNMEZ)
               & alan.gorunur(sscl, so_nir, so_sw, gorunmez=alan.SONRA_GORUNMEZ))
    d = alan.dnbr(alan.nbr(on_nir, on_sw), alan.nbr(so_nir, so_sw))
    sonuc = alan.yanan_alan(d, gecerli, arama)
    esikler = alan.tum_esikler(d, gecerli, arama)
    yanik = alan.toparla(arama & gecerli & (d >= alan.ANA_ESIK))
    temiz_ha = float(yanik.sum() * alan.PIKSEL_M2 / 1e4)

    # görseller (10 m'lik doğal renk karosu, küçültülmüş ızgarada)
    k = max(1, math.ceil(max(w, h) / GORSEL_EN))
    gw, gh = math.ceil(w / k), math.ceil(h / k)
    gt = from_origin(transform.c, transform.f, RES * k, RES * k)
    os.makedirs(gorsel_dizin, exist_ok=True)
    jpg(oku(og, "visual", crs, gt, gw, gh, Resampling.average), f"{gorsel_dizin}/{olay['id']}_once.jpg")
    jpg(oku(sg, "visual", crs, gt, gw, gh, Resampling.average), f"{gorsel_dizin}/{olay['id']}_sonra.jpg")
    km = kucult_maske(yanik, k)[:gh, :gw]
    rgba = np.zeros((gh, gw, 4), np.uint8); rgba[km] = (215, 48, 31, 170)
    Image.fromarray(rgba, "RGBA").save(f"{gorsel_dizin}/{olay['id']}_yanik.png", optimize=True)

    # yeşillenme: yanan alan ve yanmamış bitkili çevre
    ndvi_once = alan.ndvi(on_nir, oku(og, "red", crs, transform, w, h))
    cevre = gecerli & ~arama & (d < alan.ESIKLER["genis"]) & (ndvi_once >= 0.4)
    son_ndvi = alan.ndvi(so_nir, oku(sg, "red", crs, transform, w, h))
    gs = alan.gorunur(sscl, so_nir, gorunmez=alan.SONRA_GORUNMEZ)
    hemen = {"yil": bas.year, "tarih": st, "hemen_sonra": True,
             "yanik": round(float(np.nanmean(son_ndvi[yanik & gs])), 3),
             "cevre": round(float(np.nanmean(son_ndvi[cevre & gs])), 3), "gorunur": round(so, 3)}
    egri = yesillenme(ak, crs, transform, w, h, yanik, cevre, dt.date.fromisoformat(ot), bas.year)

    inv = Transformer.from_crs(crs, 4326, always_xy=True)
    x0, y1 = transform.c, transform.f; x1, y0 = x0 + w * RES, y1 - h * RES
    lo0, la0 = inv.transform(x0, y0); lo1, la1 = inv.transform(x1, y1)
    return {**{k2: v for k2, v in olay.items() if k2 != "noktalar"},
            "once_tarih": ot, "sonra_tarih": st,
            "once_gorunur": round(oo, 3), "sonra_gorunur": round(so, 3),
            "yanik_ha": round(temiz_ha), "ham_yanik_ha": round(sonuc["ha"]),
            "esik_ha": {a: round(v) for a, v in esikler.items()},
            "gorunmez_oran": round(sonuc["gorunmez_oran"], 3),
            "arama_ha": round(sonuc["arama_piksel"] * alan.PIKSEL_M2 / 1e4),
            "cevre_piksel": int(cevre.sum()),
            "gorsel_kutu": [round(lo0, 4), round(la0, 4), round(lo1, 4), round(la1, 4)],
            "gorsel_boyut": [gw, gh], "yesillenme": sorted(egri + [hemen], key=lambda r: r["tarih"])}


def yesillenme(ak, crs, transform, w, h, yanik, cevre, once_tarih, yangin_yili):
    """Her yıl yangın öncesi görüntüyle aynı mevsimde (±40 gün) en açık günü bulur;
    yanan alanın ve yanmamış çevrenin ortalama NDVI'ını verir."""
    out = []
    bugun = dt.date.today()
    yillar = [yangin_yili - 1] + list(range(yangin_yili + 1, bugun.year + 1))

    def bir_yil(y):
        try:
            merkez = once_tarih.replace(year=y)
        except ValueError:
            merkez = once_tarih.replace(year=y, day=28)
        b, s = merkez - dt.timedelta(days=40), min(bugun, merkez + dt.timedelta(days=40))
        if b > bugun:
            return None
        gunler = ara(ak, b.isoformat(), s.isoformat(), bulut=50)
        sec_ = sec(gunler, crs, transform, w, h, yanik, alan.SONRA_GORUNMEZ, ilk_yeterli=None, yakin=merkez.isoformat())
        if not sec_ or sec_[1] < 0.8:
            return None
        t, oran, og, scl = sec_
        nir = oku(og, "nir08", crs, transform, w, h); red = oku(og, "red", crs, transform, w, h)
        g = alan.gorunur(scl, nir, red, gorunmez=alan.SONRA_GORUNMEZ)
        n = alan.ndvi(nir, red)
        a = n[yanik & g]; c = n[cevre & g]
        if len(a) < 50 or len(c) < 50:
            return None
        return {"yil": y, "tarih": t, "yanik": round(float(np.nanmean(a)), 3), "cevre": round(float(np.nanmean(c)), 3),
                "gorunur": round(oran, 3)}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(bir_yil, yillar):
            if r:
                out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=12)
    ap.add_argument("--id", default=None)
    ap.add_argument("--yeniden", action="store_true", help="ölçülmüş olayları da yeniden ölç")
    a = ap.parse_args()
    adaylar = json.load(open("veri/olay_adaylari.json", encoding="utf8"))[: a.adet]
    eski = {}
    if os.path.exists("veri/olaylar.json"):
        eski = {o["id"]: o for o in json.load(open("veri/olaylar.json", encoding="utf8"))}
    sonuc = []
    for ol in adaylar:
        if a.id and ol["id"] != a.id:
            if ol["id"] in eski:
                sonuc.append(eski[ol["id"]])
            continue
        if ol["id"] in eski and not a.yeniden and not a.id:
            sonuc.append(eski[ol["id"]]); continue
        if (dt.date.today() - dt.date.fromisoformat(ol["son"])).days < 12:
            print(ol["id"], "yeni bitti ya da sürüyor; temiz 'sonra' görüntüsü için bekleniyor"); continue
        print(ol["id"], ol["il"], ol["ilce"], ol["bas"], ol["son"], flush=True)
        t0 = time.time()
        r = olc(ol)
        if r:
            print(f"  yanık {r['yanik_ha']} ha (eşik {alan.ANA_ESIK}), {time.time()-t0:.0f} sn", flush=True)
            sonuc.append(r)
        json.dump(sonuc, open("veri/olaylar.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(sonuc, open("veri/olaylar.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
