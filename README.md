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

Erken. Şu an elde olan:

- EVDS istemcisi (`client.py`) — seri çekme, eksik gözlem ve
  tip dönüşümü dahil
- Türkçe metin normalizasyonu (`text.py`)

Henüz olmayan: MCP katmanının kendisi, seri kataloğu ve arama. Sıradaki
iş onlar. Ertelediğim her şey `SONRA.md` içinde.

## Kurulum

```
git clone https://github.com/<kullanici>/evds-mcp
cd evds-mcp
uv sync
```

API anahtarını [evds2.tcmb.gov.tr](https://evds2.tcmb.gov.tr) adresinden
ücretsiz alıyorsun:

```
export EVDS_API_KEY=...
```

## Kullanım

```python
from datetime import date
from evds_mcp.client import EVDS

with EVDS() as evds:
    seriler = evds.veri(
        ["TP.FG.J0"],
        baslangic=date(2020, 1, 1),
        bitis=date(2026, 8, 1),
        frekans="aylık",
    )

for g in seriler[0].gozlemler[:5]:
    print(g.tarih, g.deger)
```

## Notlar

Uğraştıran birkaç şey, aynı yola girecekler için:

**Türkçe küçük harf.** `"FAİZ".lower()` beklediğin şeyi vermiyor —
`"I".lower()` size `"i"` döndürüyor, `"ı"` değil. Aramada bunu
kullanırsanız hata almıyorsunuz, sadece sonuç gelmiyor. `text.py`
bunun için var.

**Tarih formatı `GG-AA-YYYY`.** ISO değil. Karıştırırsanız API hata
vermiyor, sessizce başka bir aralık dönüyor.

**Sütun adlarında nokta yerine alt çizgi.** `TP.FG.J0` istiyorsunuz,
yanıtta `TP_FG_J0` geliyor. İkisini de arıyoruz.

**Anahtar 2024'ten beri header'da**, URL parametresinde değil. Eski
örnekler hâlâ URL'de gösteriyor.

## Testler

```
uv run pytest
```

Testler ağa çıkmıyor, `tests/fixtures/` altındaki kayıtlı yanıtlara
karşı çalışıyor. Fixture şu an elle yazıldı; gerçek bir yanıtla
değiştirilecek.

## Lisans

MIT
