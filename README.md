# Orman yangınları uzaydan

NASA uydularının 2001'den bu yana Türkiye'de gördüğü yangın noktaları; en büyük yangınlarda
Sentinel-2 ile ölçülen yanmış alan ve yıllara göre yeniden yeşillenme.

Site: https://birtohum.github.io/orman-yanginlari-uzaydan/

## Veri akışı

| Adım | Dosya | Ne yapar |
|---|---|---|
| 1 | `indir.py` | FIRMS ülke yıllık arşivleri (MODIS 2001+, VIIRS S-NPP 2012+; anahtarsız), geoBoundaries il/ilçe sınırları |
| 2 | `guncel.py` | Bu yılın tespitleri: FIRMS'in açık "son 7 gün" dosyaları + (anahtar varsa) FIRMS API ile yılbaşından bugüne |
| 3 | `tespit.py` | Süzme (sabit kaynak, deniz üstü, düşük güven), il/ilçe ataması, ESA WorldCover 2020 ile orman/tarla sınıfı |
| 4 | `uret.py` | Site verisi (`site/veri/`), büyük yangın adayları (yer-zaman kümeleme, `olaylar.py`) |
| 5 | `uydu.py` | Sentinel-2 L2A (Earth Search STAC) pencere okuma: önce/sonra görüntüsü, dNBR yanık alanı, NDVI yeşillenme eğrisi |

Yanık alanı matematiği `alan.py`'de (ağ yok); testler `testler/`:

```
python -m pytest -q
```

`veri/arazi.png`: ESA WorldCover 2020'nin Türkiye için ~150 m'lik, 4 sınıfa indirgenmiş kopyası
(`python -c "import konum; konum.worldcover_indir()"` ile yeniden üretilir).

## FIRMS anahtarı (isteğe bağlı)

Geçmiş yıllar anahtarsız gelir. İçinde bulunulan yılın tamamı için ücretsiz bir FIRMS MAP_KEY gerekir:

1. https://firms.modaps.eosdis.nasa.gov/api/map_key/ adresinden e-postanla anahtar iste.
2. Yerelde proje klasörüne `.env` dosyası: `FIRMS_MAP_KEY=anahtarın`
3. GitHub'da: Settings → Secrets and variables → Actions → New repository secret,
   ad `FIRMS_MAP_KEY`, değer anahtarın.

Anahtar yoksa günlük iş yalnız son 7 günü ekler (her gün çalıştığı için o günden sonrası eksiksiz birikir).

## Sınırlar

- Uydu noktası yangın sayısı değildir: tarla anızı, çöplük, sanayi ısısı da görünür. FIRMS'in sabit kaynak
  işaretli noktaları atılır; tarla yakmaları kalır ve ayrıca gösterilir.
- VIIRS pikseli ~375 m, MODIS ~1 km; iki uydunun sayıları toplanmaz.
- Bulut altındaki yangın görülmez; Sentinel-2'de bulutlu pikseller sayılmaz, yanık alanı alt sınırdır.
- OGM resmî istatistikleri saha kayıtlarıdır ve başka şeyi ölçer; farklı çıkması beklenir.

## Lisans

Kod Apache-2.0. Veri: NASA FIRMS, Copernicus Sentinel-2 (ESA), ESA WorldCover (CC BY 4.0),
geoBoundaries / OpenStreetMap (ODbL).
