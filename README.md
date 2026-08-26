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

Çalışıyor. Beş araç var: üçü veri, ikisi metodoloji.

Henüz yok: kalıcı önbellek, TÜİK, anlamsal arama, tahmin araçları.
Ertelediğim her şey `SONRA.md` içinde.

## Kurulum

```
git clone https://github.com/<kullanici>/evds-mcp
cd evds-mcp
uv sync
```

API anahtarını [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr) adresinden
ücretsiz alıyorsun — profil sayfasının altındaki "API Anahtarı Kopyala".

## MCP'ye bağlama

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

Sonrası konuşma dilinde:

> 2025'te TÜFE ne kadar arttı?

## Araçlar

**`search_series`** — Türkçe ya da İngilizce kavram ver, seri kodlarını
bulur. Her iş buradan başlıyor, çünkü kodları kimse ezbere bilmiyor.
Dönen künyede kapsam tarihleri de var; EVDS'de yayını durmuş çok sayıda
arşiv serisi duruyor, hangisinin canlı olduğu oradan görülüyor.

**`summarize_series`** — Ham veriyi dökmeden bakar: gözlem sayısı, eksik
veri, min, max, ortalama, toplam değişim.

**`get_series`** — Veriyi getirir, birden fazla kod alabilir.
Varsayılan olarak özet ve son 24 gözlem döner. Bu bir kısıtlama değil
tasarım: 2003'ten beri aylık bir seri 280 gözlem eder, üç seri istendiğinde
bağlam sayıyla dolar ve model düzgün düşünemez. Tamamı gerekiyorsa
`full=True`.

**`test_stationarity`** — Seriyi durağanlaştıran en düşük dereceli
dönüşümü bulur. ADF'yi seviyede, log farkında ve ardışık farklarda
çalıştırır, I(d) derecesini söyler.

**`analyze_relationship`** — İki seri arasındaki ilişkiyi verir, ama
önce her ikisini durağanlık testinden geçirip gereken dönüşümü uygular
ve hangi dönüşümü uyguladığını yazar. İkisi de I(1) ise eşbütünleşmeyi
de test eder.

### Neden ham korelasyon aracı yok

Bu bir eksiklik değil, tasarımın kendisi. Ölçtüm: TÜFE ile politika faizi
**seviyelerinde korelasyon 0.86**. Bir model buradan "güçlü ilişki" der.
Ama iki seri de durağan değil — bu sahte regresyonun ders kitabı örneği.
Durağanlaştırıldıktan sonra korelasyon **0.03**.

Model bu farkı kendiliğinden görmüyor. O yüzden yanlış rakama giden yol
hiç açılmıyor: seviye korelasyonu hesaplayan bir araç sunmuyorum.
`analyze_relationship` ham rakamı yine de gösteriyor, ama "bunu kullanma"
etiketiyle ve nedeniyle birlikte.

Bir de Türkiye'ye özel olan kısım: TÜFE bu dönemde **I(2)**. Yani bir fark
yetmiyor, log farkı da yetmiyor. Modelin ezberindeki "fiyat endeksinde log
farkı al" kuralı burada yanlış cevap üretiyor. Ölçümlerin tamamı
`ASAMA2.md` içinde.

## Python'dan

```python
from datetime import date
from evds_mcp.client import EVDS
from evds_mcp.catalog import Katalog

with EVDS() as evds:
    k = Katalog(evds)

    k.grup_ara("enflasyon")
    # bie_tukfiy2025  Tüketici Fiyat Endeksi (2025=100)  [AYLIK]

    k.seri_ara("genel", "bie_tukfiy2025")
    # TP.TUKFIY2025.GENEL  Genel Endeks  01-01-2005 - 01-07-2026

    evds.veri(["TP.TUKFIY2025.GENEL"], date(2025, 1, 1), date(2025, 5, 1))
```

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
koyuyor ve servis anlamıyor.

**Toplu seri ucu yok.** 676 veri grubu var ve serileri ancak grup kodu
vererek çekebiliyorsunuz. Bu yüzden arama iki seviyeli: önce grup, sonra
grup içinde seri.

**Sütun adlarında nokta yerine alt çizgi.** `TP.FG.J0` istiyorsunuz,
yanıtta `TP_FG_J0` geliyor.

**Tarih formatı `GG-AA-YYYY`.** ISO değil. Karıştırırsanız API hata
vermiyor, sessizce başka bir aralık dönüyor — en sinsi olanı bu.

**Anahtar 2024'ten beri header'da**, URL parametresinde değil.

**Türkçe küçük harf.** `"FAİZ".lower()` beklediğinizi vermiyor;
`"I".lower()` size `"i"` döndürüyor, `"ı"` değil. Aramada bunu
kullanırsanız hata almıyorsunuz, sadece sonuç gelmiyor.

**Uluslararası gruplar ülkeleri alfabetik diziyor.** "politika faizi"
araması Almanya'yı getirip Türkiye'yi 470. sıraya gömüyordu. Sıralamada
Türkiye eşitlik bozucu.

Bir de yanlış alarm: yanıtlardaki Türkçe karakterler bozuk *görünüyor*
ama değil. Geçerli UTF-8 geliyor; bozan şey Windows konsolunun kod sayfası.

## Testler

```
uv run pytest          # cevrimdisi, fixture'lara karsi
uv run pytest -m live  # gercek API, EVDS_API_KEY gerekiyor
```

`tests/fixtures/` altındakiler gerçek EVDS yanıtları. Servis şekil
değiştirirse önce bu testler kırılır.

## Lisans

MIT
