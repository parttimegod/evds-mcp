# İlişki analizi notları

Araç, bir korelasyon sayısını dönüşüm ve test sonuçlarıyla birlikte
döndürüyor. Amaç, serinin seviyesiyle farkını karşılaştırırken hangi
hesabın yapıldığını görünür tutmak.

## Önceki örnek

USD/TRY (`TP.DK.USD.A.YTL`) ile TÜFE (`TP.TUKFIY2025.GENEL`),
aylık, Ocak 2010–Haziran 2026 için önceki geliştirme notlarında şu
sonuçlar kaydedilmişti:

| Hesap | Korelasyon |
| --- | ---: |
| Seviyeler | 0.9856 |
| İki seriye de ikinci fark | 0.1546 |
| Log farkı, kur bir gözlem önde | 0.5685 |

Aynı notlarda TÜFE için seviye ADF p-değeri 0.9973, ilk fark 0.9920,
ikinci fark 0.0000 olarak yuvarlanmış ve log farkı 0.3512 verilmişti.
Bu örneklem ve ayarlarda araç TÜFE'yi I(2) olarak sınıfladı. Buradan
Türkiye TÜFE'sinin her dönemde kesin olarak I(2) olduğu sonucu çıkmaz.

Bu sayılar tarihsel notlardır. Kullanılan tam veri görüntüsü repoda
saklanmadı ve bu incelemede canlı API ile yeniden hesaplanmadı.
Revizyonlar ve test sürümleri sonucu değiştirebilir. Yüksek bir seviye
korelasyonu tek başına ilişkinin sahte olduğunu, yüksek gecikmeli
korelasyon da kur geçişkenliğini kanıtlamaz.

## Şimdiki hesap

`analysis.py`, statsmodels ADF testini sabit terim ve AIC gecikme seçimiyle
çalıştırıyor. Eşik %5. Önce seviye, pozitif serilerde log farkı, ardından
en fazla üç ardışık fark deneniyor. Log farkının testi eşiği geçerse
o dönüşüm tercih ediliyor; aksi durumda ilk reddeden fark derecesi
kullanılıyor.

ADF'nin sıfır hipotezi birim köktür. Reddedilememesi kesin birim kök
kanıtı değildir. Örneklem uzunluğu, deterministik terimler ve kırılmalar
ayrıca değerlendirilmeli. Kullanılan testin ayrıntıları
[statsmodels ADF dokümanında](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html).

İki seri için otomatik dönüşüm, önerilen derecelerin yüksek olanını
kullanıyor. Bu ortak kural diğer seriyi aşırı farklayabilir.
`transform` ile bir alternatif verilebilir; mevcut ADF sonucu
uygunsuzsa uyarı döner.

İki seri de I(1) sınıflandığında
[Engle–Granger testi](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.coint.html)
çalışır. `var` ve `yok` alanları %5 eşiğinin kısa gösterimidir,
kesin varlık/yokluk hükmü değildir.

Gecikme taraması aynı örneklemde en yüksek mutlak korelasyonu seçer.
Çoklu karşılaştırma düzeltmesi ve dış örneklem kontrolü yok.
Eksik tarih çiftleri atıldığı için gecikme kalan gözlem sayısını izler;
bir gözlem her zaman bir takvim ayı değildir.

## Yeniden çalıştırma

Geçerli `EVDS_API_KEY` ortam değişkeniyle, repo kökünde:

```bash
uv run python - <<'PY'
import json
from evds_mcp.server import analyze_relationship

result = analyze_relationship(
    codes=["TP.DK.USD.A.YTL", "TP.TUKFIY2025.GENEL"],
    start="2010-01-01",
    end="2026-06-01",
    frequency="monthly",
    transform="logd1",
    max_lag=6,
)
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
```

Bu komut güncel API verisini kullanır; yukarıdaki tarihsel sayıları
birebir tekrar etmesi beklenmemeli.
