# evds-mcp

TCMB'nin EVDS verisini bir dil modelinin doğrudan kullanabilmesi için
yazdığım MCP sunucusu.

## Neden

EVDS'den veri almak şöyle bir şey: siteye gir, menülerde seriyi ara,
kodunu bul (`TP.FG.J0` gibi, kimsenin ezberinde değil), tarih aralığı seç,
Excel indir, aç, temizle, Python'a al. Yirmi dakika geçmiş oluyor ve daha
tek satır analiz yazmadın.

Claude'a sorayım desen o da bilmiyor — TCMB verisine erişimi yok, ya
"ulaşamıyorum" diyor ya da uyduruyor.

Bu paket araya giriyor. "2020'den beri TÜFE ve politika faizini getir"
diyorsun, gidip getiriyor.

## Durum

Erken. Şu an çalışan:

- EVDS istemcisi — seri verisi, veri grubu listesi, gruptaki seriler
- Katalog ve arama — 676 veri grubu içinde puanlı arama, grup içinde seri arama
- Türkçe metin normalizasyonu

Henüz olmayan: MCP katmanının kendisi. Sıradaki iş o. Ertelediğim her şey
`SONRA.md` içinde.

## Kurulum

```
git clone https://github.com/<kullanici>/evds-mcp
cd evds-mcp
uv sync
```

API anahtarını [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr) adresinden
ücretsiz alıyorsun — profil sayfasının altındaki "API Anahtarı Kopyala".

```
export EVDS_API_KEY=...
```

## Kullanım

```python
from datetime import date
from evds_mcp.client import EVDS

with EVDS() as evds:
    tufe, faiz = evds.veri(
        ["TP.FG.J0", "TP.APIFON4"],
        baslangic=date(2024, 1, 1),
        bitis=date(2024, 6, 1),
    )

for a, b in zip(tufe.gozlemler, faiz.gozlemler):
    print(a.tarih, a.deger, b.deger)
```

```
2024-1 1984.02 44.0
2024-2 2073.88 45.0
2024-3 2139.47 51.22
...
```

Aramayla birlikte tam döngü:

```python
from evds_mcp.catalog import Katalog

with EVDS() as evds:
    k = Katalog(evds)

    gruplar = k.grup_ara("enflasyon")
    # bie_tukfiy2025  Tüketici Fiyat Endeksi (2025=100)  [AYLIK]

    seriler = k.seri_ara("genel", "bie_tukfiy2025")
    # TP.TUKFIY2025.GENEL  Genel Endeks  01-01-2005 - 01-07-2026

    evds.veri(["TP.TUKFIY2025.GENEL"], date(2025, 1, 1), date(2025, 5, 1))
```

Künyede kapsam tarihleri de var, çünkü EVDS'de bir sürü arşivlenmiş seri
duruyor; hangisinin hâlâ yayınlandığını veriyi çekmeden görmek gerekiyor.

## Notlar

Uğraştıran şeyler. Aynı yola girecekler buradan zaman kazansın.

**Servis evds3'e taşınmış.** İnternetteki örneklerin neredeyse tamamı
hâlâ `evds2.tcmb.gov.tr/service/evds/` gösteriyor. O adres artık web
arayüzüne yönlendiriyor ve elinize JSON yerine HTML geçiyor. Doğrusu:

```
https://evds3.tcmb.gov.tr/igmevdsms-dis/
```

**Parametreler soru işareti olmadan yola ekleniyor.** Normal query string
değil:

```
.../igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2020&type=json
```

`requests` ya da `httpx`'in `params=` parametresini kullanırsanız başa `?`
koyuyor ve servis anlamıyor. URL'yi elle kurmak gerekiyor.

**Sütun adlarında nokta yerine alt çizgi.** `TP.FG.J0` istiyorsunuz,
yanıtta `TP_FG_J0` geliyor. İkisine de bakıyoruz.

**Tarih formatı `GG-AA-YYYY`.** ISO değil. Karıştırırsanız API hata
vermiyor, sessizce başka bir aralık dönüyor — en sinsi olanı bu.

**Anahtar 2024'ten beri header'da**, URL parametresinde değil.

**Türkçe küçük harf.** `"FAİZ".lower()` beklediğinizi vermiyor;
`"I".lower()` size `"i"` döndürüyor, `"ı"` değil. Aramada bunu
kullanırsanız hata almıyorsunuz, sadece sonuç gelmiyor. `text.py` bunun
için var.

Bir de yanlış alarm: yanıtlardaki Türkçe karakterler bozuk *görünüyor*
ama değil. Üç uçta da geçerli UTF-8 geliyor; bozan şey Windows
konsolunun kod sayfası.

## Testler

```
uv run pytest          # cevrimdisi, fixture'lara karsi
uv run pytest -m live  # gercek API, EVDS_API_KEY gerekiyor
```

`tests/fixtures/` altındakiler gerçek EVDS yanıtları, bir kez kaydedildi.
Servis şekil değiştirirse önce bu testler kırılır.

## Lisans

MIT
