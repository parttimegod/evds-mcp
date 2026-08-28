# evds-mcp

TCMB EVDS verisi için MCP sunucusu. Dil modeli seri arayabiliyor, veri
çekebiliyor ve iki seri arasındaki ilişkiyi durağanlık testinden
geçirerek analiz edebiliyor.

## Kurulum

```
git clone https://github.com/parttimegod/evds-mcp
cd evds-mcp
uv sync
```

API anahtarı [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr) üzerinden
ücretsiz alınıyor: profil sayfasının altında "API Anahtarı Kopyala".

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
| `search_series` | Kavramdan seri kodu bulur. Künyede ad, frekans, kaynak ve kapsam tarihleri döner. |
| `summarize_series` | Gözlem sayısı, eksik veri, min, max, ortalama, toplam değişim. Ham veri döndürmez. |
| `get_series` | Veri. Varsayılan: özet + son 24 gözlem. Tamamı için `full=True`. Birden fazla kod alır. |
| `test_stationarity` | ADF'yi seviyede, log farkında ve ardışık farklarda çalıştırır. I(d) derecesini ve önerilen dönüşümü döndürür. |
| `analyze_relationship` | İki seri arası ilişki. Durağanlık testi yapar, dönüşümü uygular, hangisini uyguladığını yazar. İkisi de I(1) ise eşbütünleşme testi. `max_lag`, `transform`. |

`get_series` varsayılanı dar: 2003'ten beri aylık bir seri 280 gözlem
eder, birkaç seri istendiğinde bağlam dolar.

## Ham korelasyon aracı yok

Seviye korelasyonu hesaplayan araç bulunmuyor. İki seriyi
karşılaştırmanın tek yolu `analyze_relationship` ve o durağanlık
testini kendi içinde yapıyor.

Ölçüm — USD/TRY ile TÜFE, aylık, 2010-01 – 2026-06:

| Yöntem | Korelasyon |
|---|---|
| Seviye | 0.99 |
| Otomatik dönüşüm (d2) | 0.15 |
| Log farkı, 1 ay gecikmeli | 0.57 |

Seviye korelasyonu sahte: iki seri de durağan değil (ADF p = 1.00 ve
0.99), ortak trend rakamı şişiriyor.

d2 aşırı farklanmış: USD/TRY I(1), TÜFE I(2). Araç ikisini de ikinci
dereceden farklayınca sinyal zayıflıyor.

Üçüncüsü yüzde değişim üzerinden ve gecikmeli. Kur geçişkenliği tepesi
1. ayda:

```
gecikme 0 : +0.42
gecikme 1 : +0.57
gecikme 2 : +0.34
gecikme 3 : +0.21
```

`analyze_relationship` ham seviye rakamını yine döndürüyor, "kullanma"
uyarısıyla birlikte. Dönüşüm `transform` ile elle verilebiliyor,
gecikme `max_lag` ile taranıyor.

TÜFE'nin bu dönemde I(2) çıkması Türkiye'ye özgü: ne bir fark ne log
farkı durağanlaştırıyor. ADF çıktılarının tamamı [ASAMA2.md](ASAMA2.md)
içinde.

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

## EVDS API notları

**Servis evds3'te.** Yaygın örnekler hâlâ
`evds2.tcmb.gov.tr/service/evds/` gösteriyor; o adres web arayüzüne
yönlendiriyor, JSON yerine HTML dönüyor. Doğrusu:
`https://evds3.tcmb.gov.tr/igmevdsms-dis/`

**Parametreler yola ekleniyor**, query string değil:
`.../igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2020&type=json`
`params=` kullanıldığında başa `?` geliyor ve servis anlamıyor.

**Toplu seri ucu yok.** 676 veri grubu var, seriler ancak grup kodu
verilerek çekiliyor. Arama bu yüzden iki seviyeli: önce grup, sonra
grup içinde seri.

**Sütun adlarında nokta yerine alt çizgi.** İstek `TP.FG.J0`, yanıt
`TP_FG_J0`.

**Tarih formatı `GG-AA-YYYY`.** ISO değil. Yanlış format hata
döndürmüyor, sessizce başka bir aralık dönüyor.

**Anahtar 2024'ten beri HTTP header'ında**, URL parametresinde değil.

**Türkçe küçük harf.** `"I".lower()` → `"i"`, `"ı"` değil. Aramada
kullanılırsa hata alınmıyor, sonuç dönmüyor. `text.py` bunun için.

**Uluslararası gruplar alfabetik sıralı.** "politika faizi" araması
Türkiye'yi 470. sıraya düşürüyordu; sıralamada Türkiye eşitlik bozucu.

**Türkçe karakterler bozuk görünebilir ama değil.** Yanıtlar geçerli
UTF-8; sorun Windows konsolunun kod sayfası.

## Testler

```
uv run pytest          # cevrimdisi, fixture'lara karsi
uv run pytest -m live  # gercek API, EVDS_API_KEY gerekiyor
```

`tests/fixtures/` gerçek EVDS yanıtları. Servis şekil değiştirirse
önce bu testler kırılır.

## Lisans

MIT
