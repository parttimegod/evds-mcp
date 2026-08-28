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

USD/TRY ~ TÜFE, aylık, 2010-01 – 2026-06:

| Yöntem | Korelasyon | Durum |
|---|---|---|
| Seviye | 0.99 | Sahte regresyon. ADF p = 1.00 ve 0.99, ikisi de durağan değil |
| Otomatik dönüşüm (d2) | 0.15 | Aşırı farklanmış. USD/TRY I(1), TÜFE I(2) |
| Log farkı + 1 ay gecikme | 0.57 | — |

Gecikme profili:

```
0 ay  +0.42
1 ay  +0.57
2 ay  +0.34
3 ay  +0.21
```

`analyze_relationship` ham seviye rakamını "kullanma" uyarısıyla
döndürür. `transform` dönüşümü elle seçer, `max_lag` gecikme tarar.

TÜFE bu dönemde I(2): ne birinci fark ne log farkı durağan. ADF
çıktıları [ASAMA2.md](ASAMA2.md) içinde.

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

## EVDS API

```
endpoint    https://evds3.tcmb.gov.tr/igmevdsms-dis/
kimlik      HTTP header: key: <anahtar>          (2024 öncesi URL'deydi)
biçim       .../igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2020&type=json
tarih       GG-AA-YYYY
uçlar       datagroups/mode=0&code=&type=json    676 veri grubu
            serieList/type=json&code=<grup>      gruptaki seriler
```

| Davranış | Sonuç |
|---|---|
| `evds2.tcmb.gov.tr/service/evds/` | Web arayüzüne yönlenir, HTML döner |
| `params=` ile istek | Başa `?` eklenir, servis anlamaz |
| Toplu seri ucu | Yok. Seriler grup kodu ile çekilir |
| İstenen `TP.FG.J0` | Yanıt sütunu `TP_FG_J0` |
| Geçersiz tarih formatı | Hata yok, farklı aralık döner |
| Uluslararası grup sıralaması | Alfabetik; Türkiye 470. sırada kalabilir |

Python tarafında `"I".lower()` → `"i"` (`"ı"` değil), `"İ".lower()` →
`i` + U+0307. Arama anahtarı üretimi `text.py` içinde.

Yanıtlar UTF-8. Türkçe karakterler bozuk görünüyorsa sebep Windows
konsolunun kod sayfası.

## Testler

```
uv run pytest          # cevrimdisi, fixture'lara karsi
uv run pytest -m live  # gercek API, EVDS_API_KEY gerekiyor
```

`tests/fixtures/` gerçek EVDS yanıtları. Servis şekil değiştirirse
önce bu testler kırılır.

## Lisans

MIT
