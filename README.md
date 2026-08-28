# evds-mcp

TCMB EVDS verilerine erişim sağlayan MCP sunucusu. Claude ve diğer MCP
destekli istemcilerden Türkiye makroekonomik verilerini sorgulayabilir,
durağanlık testi ve ilişki analizi yapabilirsiniz.

## Özellikler

- Kavram bazlı seri arama (676 veri grubu, Türkçe ve İngilizce)
- Tek veya çoklu seri verisi çekme
- ADF durağanlık testi, bütünleşme derecesi tespiti
- İki seri arası ilişki analizi: otomatik dönüşüm, gecikme taraması,
  Engle-Granger eşbütünleşme testi
- Türkçe karakter normalizasyonu

## Gereksinimler

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- EVDS API anahtarı (ücretsiz)

## Kurulum

```bash
git clone https://github.com/parttimegod/evds-mcp
cd evds-mcp
uv sync
```

API anahtarını almak için [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr)
adresine kaydolun. Profil sayfasının altındaki "API Anahtarı Kopyala"
butonunu kullanın.

## Yapılandırma

MCP istemcinizin yapılandırma dosyasına ekleyin:

```json
{
  "mcpServers": {
    "evds": {
      "command": "uv",
      "args": ["--directory", "/path/to/evds-mcp", "run", "evds-mcp"],
      "env": { "EVDS_API_KEY": "your-api-key" }
    }
  }
}
```

Claude Desktop için `claude_desktop_config.json`, Claude Code için
`~/.claude.json` dosyasını düzenleyin.

## Kullanım

Yapılandırdıktan sonra doğal dille sorabilirsiniz:

```
2020'den beri TÜFE ve politika faizini getir
Konut fiyat endeksi hangi tarihten beri yayınlanıyor?
Dolar kuru ile enflasyon arasında ilişki var mı?
```

## Araçlar

### `search_series(query, limit=10)`

Kavramdan seri kodu bulur. Seri kodları (`TP.FG.J0` gibi) ezberlenmediği
için arama buradan başlar.

Dönen alanlar: kod, ad, İngilizce ad, veri grubu, frekans, kaynak,
kapsam tarihleri.

### `summarize_series(code, start, end, frequency="aylık")`

Seriyi ham veri döndürmeden özetler: gözlem sayısı, eksik veri, ilk ve
son değer, min, max, ortalama, toplam değişim.

### `get_series(codes, start, end, frequency="aylık", full=False)`

Seri verisini getirir. Birden fazla kod verilebilir, aynı tarih
ızgarasına hizalı döner.

Varsayılan olarak özet ve son 24 gözlem döner. 2003'ten beri aylık bir
seri 280 gözlem içerir ve birkaç seri birlikte istendiğinde bağlam
penceresini doldurur. Tüm gözlemler için `full=True` kullanın.

### `test_stationarity(code, start, end, frequency="aylık")`

ADF testini seviyede, log farkında ve ardışık farklarda çalıştırır.
Bütünleşme derecesini I(d) ve önerilen dönüşümü döndürür.

### `analyze_relationship(codes, start, end, frequency="aylık", transform=None, max_lag=0)`

İki seri arasındaki ilişkiyi analiz eder. Önce her iki seriyi durağanlık
testinden geçirir, gereken dönüşümü uygular ve hangi dönüşümü
uyguladığını çıktıda belirtir. Her iki seri de I(1) ise Engle-Granger
eşbütünleşme testi çalıştırır.

- `transform` — dönüşümü elle seçer (`logd1`, `d1`, `d2`, `seviye`)
- `max_lag` — gecikmeli ilişki tarar, en güçlü gecikmeyi bildirir

## Neden ham korelasyon aracı yok

Seviye korelasyonu hesaplayan ayrı bir araç bulunmuyor. Makroekonomik
seriler genellikle durağan değildir ve seviye korelasyonu ortak trend
nedeniyle yanıltıcı sonuç verir.

USD/TRY ve TÜFE, aylık, 2010-01 – 2026-06:

| Yöntem | Korelasyon | Not |
|---|---|---|
| Seviye | 0.99 | Sahte regresyon (ADF p = 1.00 ve 0.99) |
| Otomatik dönüşüm (d2) | 0.15 | Aşırı farklanmış: USD/TRY I(1), TÜFE I(2) |
| Log farkı + 1 ay gecikme | 0.57 | |

Gecikme profili:

```
0 ay  +0.42
1 ay  +0.57
2 ay  +0.34
3 ay  +0.21
```

`analyze_relationship` seviye korelasyonunu yine döndürür, uyarı
etiketiyle birlikte.

TÜFE bu dönemde I(2)'dir; ne birinci fark ne de log farkı seriyi
durağanlaştırır. ADF çıktılarının tamamı [ASAMA2.md](ASAMA2.md)
dosyasındadır.

## Python API

```python
from datetime import date
from evds_mcp.client import EVDS
from evds_mcp.catalog import Katalog

with EVDS() as evds:
    k = Katalog(evds)

    k.grup_ara("enflasyon")                # bie_tukfiy2025
    k.seri_ara("genel", "bie_tukfiy2025")  # TP.TUKFIY2025.GENEL

    seriler = evds.veri(
        ["TP.TUKFIY2025.GENEL"],
        date(2025, 1, 1),
        date(2025, 5, 1),
    )
```

## EVDS API notları

Servis endpoint'i:

```
https://evds3.tcmb.gov.tr/igmevdsms-dis/
```

Yaygın örneklerde geçen `evds2.tcmb.gov.tr/service/evds/` adresi web
arayüzüne yönlendirir ve HTML döndürür.

| Konu | Durum |
|---|---|
| Kimlik doğrulama | HTTP header (`key`). 2024 öncesinde URL parametresiydi |
| Parametre biçimi | Yola eklenir: `.../igmevdsms-dis/series=TP.FG.J0&startDate=...` |
| `params=` kullanımı | Başa `?` ekler, servis kabul etmez |
| Tarih formatı | `GG-AA-YYYY`. Yanlış format hata vermez, farklı aralık döner |
| Toplu seri ucu | Yok. Seriler grup kodu ile çekilir |
| Sütun adları | İstek `TP.FG.J0`, yanıt `TP_FG_J0` |
| Uluslararası gruplar | Alfabetik sıralı, Türkiye 470. sırada olabilir |

Python'da `"I".lower()` sonucu `"i"` döndürür, `"ı"` değil. Türkçe
normalizasyon `text.py` içinde yapılır.

Yanıtlar UTF-8 kodlamalıdır. Türkçe karakterler bozuk görünüyorsa sebep
terminal kod sayfasıdır.

## Testler

```bash
uv run pytest          # cevrimdisi, fixture'lara karsi
uv run pytest -m live  # gercek API, EVDS_API_KEY gerekiyor
```

`tests/fixtures/` altındaki dosyalar gerçek EVDS yanıtlarıdır.

## Lisans

MIT
