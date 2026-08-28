# evds-mcp

TCMB'nin EVDS verisini bir dil modelinin doğrudan kullanabilmesi için
yazdığım MCP sunucusu.

## Neden

EVDS'den veri almak için siteye girip menülerde seriyi arıyor, kodunu
buluyor (`TP.FG.J0` gibi), Excel indirip temizliyorsun. Claude'a sorsan
o da bilmiyor; TCMB verisine erişimi yok.

Bu paket araya giriyor. "2020'den beri TÜFE ve politika faizini getir"
diyorsun, gidip getiriyor.

## Kurulum

```
git clone https://github.com/parttimegod/evds-mcp
cd evds-mcp
uv sync
```

API anahtarı [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr) üzerinden
ücretsiz: profil sayfasının altında "API Anahtarı Kopyala".

```json
{
  "mcpServers": {
    "evds": {
      "command": "uv",
      "args": ["--directory", "/evds-mcp/dizininin/yolu", "run", "evds-mcp"],
      "env": { "EVDS_API_KEY": "anahtarin" }
    }
  }
}
```

## Araçlar

| Araç | Ne yapar |
|---|---|
| `search_series` | Kavramdan seri kodu bulur. Künyede kapsam tarihleri de var; EVDS'de çok sayıda arşiv serisi duruyor. |
| `summarize_series` | Ham veri dökmeden bakar: gözlem, eksik, min, max, ortalama. |
| `get_series` | Veriyi getirir. Varsayılan olarak özet + son 24 gözlem; tamamı için `full=True`. |
| `test_stationarity` | ADF'yi seviyede, log farkında ve ardışık farklarda çalıştırıp I(d) derecesini verir. |
| `analyze_relationship` | İki seri arasındaki ilişki. Durağanlık testinden geçirir, dönüşümü uygular ve hangisini uyguladığını yazar. `max_lag`, `transform`. |

`get_series` varsayılanının dar olması bilinçli: 2003'ten beri aylık bir
seri 280 gözlem eder, birkaç seri istendiğinde bağlam sayıyla dolar.

## Ham korelasyon aracı neden yok

Seviye korelasyonu hesaplayan bir araç sunmuyorum. Sebebi bir ölçüm.

USD/TRY ile TÜFE, aylık, 2010-01 – 2026-06:

```
seviye korelasyonu             0.99
otomatik dönüşüm (d2)          0.15
log farkı, 1 ay gecikmeli      0.57
```

Üçü de aynı veriden çıkıyor. İlki sahte regresyon: iki seri de durağan
değil, ortak trend yüzünden şişkin. İkincisi aşırı farklanmış — USD/TRY
I(1) ama TÜFE bu dönemde I(2), araç ikisini de ikinci dereceden
farklayınca sinyal eriyor. Üçüncüsü iktisadi olarak doğru dönüşüm
(yüzde değişim) ve gecikmeli, çünkü kur fiyata aynı ay geçmiyor.

`analyze_relationship` ham rakamı yine gösteriyor ama "kullanma"
etiketiyle. Dönüşümü elle vermek için `transform`, gecikme taramak için
`max_lag` var.

TÜFE'nin I(2) çıkması Türkiye'ye özgü: bir fark da, log farkı da
yetmiyor. "Fiyat endeksinde log farkı al" kuralı bu seride yanlış
sonuç veriyor. ADF çıktılarının tamamı [ASAMA2.md](ASAMA2.md) içinde.

## Python'dan

```python
from datetime import date
from evds_mcp.client import EVDS
from evds_mcp.catalog import Katalog

with EVDS() as evds:
    k = Katalog(evds)
    k.grup_ara("enflasyon")                    # bie_tukfiy2025
    k.seri_ara("genel", "bie_tukfiy2025")      # TP.TUKFIY2025.GENEL
    evds.veri(["TP.TUKFIY2025.GENEL"], date(2025, 1, 1), date(2025, 5, 1))
```

## Notlar

Uğraştıran şeyler. Aynı yola girecekler zaman kazansın.

**Servis evds3'e taşınmış.** İnternetteki örneklerin neredeyse tamamı
hâlâ `evds2.tcmb.gov.tr/service/evds/` gösteriyor; o adres artık web
arayüzüne yönlendiriyor ve JSON yerine HTML dönüyor. Doğrusu
`https://evds3.tcmb.gov.tr/igmevdsms-dis/`.

**Parametreler soru işareti olmadan yola ekleniyor**, query string
değil: `.../igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2020&type=json`.
`params=` kullanırsanız başa `?` koyuyor ve servis anlamıyor.

**Toplu seri ucu yok.** 676 veri grubu var, serileri ancak grup kodu
vererek çekebiliyorsunuz. Arama bu yüzden iki seviyeli.

**Sütun adlarında nokta yerine alt çizgi:** `TP.FG.J0` istiyorsunuz,
`TP_FG_J0` geliyor.

**Tarih formatı `GG-AA-YYYY`.** ISO değil. Karıştırırsanız hata
almıyorsunuz, sessizce başka bir aralık dönüyor.

**Anahtar 2024'ten beri header'da.**

**Türkçe küçük harf.** `"I".lower()` size `"i"` veriyor, `"ı"` değil.
Aramada kullanırsanız hata almıyorsunuz, sadece sonuç gelmiyor.

**Uluslararası gruplar ülkeleri alfabetik diziyor.** "politika faizi"
araması Türkiye'yi 470. sıraya gömüyordu; sıralamada Türkiye eşitlik
bozucu.

Bir de yanlış alarm: yanıtlardaki Türkçe karakterler bozuk *görünüyor*
ama değil. Geçerli UTF-8 geliyor, bozan şey Windows konsolunun kod
sayfası.

## Testler

```
uv run pytest          # cevrimdisi, fixture'lara karsi
uv run pytest -m live  # gercek API, EVDS_API_KEY gerekiyor
```

`tests/fixtures/` altındakiler gerçek EVDS yanıtları. Servis şekil
değiştirirse önce bu testler kırılır.

## Lisans

MIT
