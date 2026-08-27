# Aşama 2 — metodoloji katmanı

Aşama 1 modele veri veriyor ama nasıl kullanacağını söylemiyor. Bu dosya,
ikinci katmanın neden gerektiğinin kanıtı. Hepsi ölçüldü, tahmin yok.

## Deney

Soru şu: "Enflasyon ile politika faizi arasında ilişki var mı?"

Veri: TP.TUKFIY2025.GENEL ve TP.BISPOLFAIZ.TUR, aylık, 2010-01 – 2026-06,
198 gözlem, eksik yok.

Aşama 1 araçları bu veriyi tertemiz getiriyor. Sorun veride değil, veriyle
ne yapıldığında.

## Modelin vereceği cevap

```
seviye korelasyonu TÜFE ~ FAİZ : +0.863
```

Bir dil modeli buradan "güçlü pozitif ilişki var" der. Rakam ikna edici
görünüyor, cümle de makul duruyor.

## Doğru cevap

```
ADF (H0 = birim kök var)
  TÜFE seviye   p = 0.9973   durağan değil
  FAİZ seviye   p = 0.2941   durağan değil

fark korelasyonu d(TÜFE) ~ d(FAİZ) : +0.158
```

İki seri de durağan değil. Yani 0.863 sahte regresyonun ders kitabı
örneği — ikisi de zamanla yukarı gittiği için birlikte hareket ediyor
görünüyorlar. Fark alındığında ilişki 0.863'ten 0.158'e düşüyor.

**Model beş kat abartılmış bir ilişkiyi kendinden emin biçimde rapor
ediyor.** Aşama 2'nin engelleyeceği şey tam olarak bu.

## Türkiye'ye özel bulgu

Standart tarif "durağan değilse bir fark al" der. Burada yetmiyor:

```
TÜFE seviye                  p = 0.9973   durağan değil
1. fark                      p = 0.9920   durağan değil
2. fark                      p = 0.0000   DURAGAN
log fark (aylık enflasyon)   p = 0.3512   durağan değil
log fark 12 (yıllık enflasyon) p = 0.6554  durağan değil
```

Bu dönemde Türkiye TÜFE'si **I(2)**. Enflasyon *oranının* kendisi bile
birim köklü, çünkü oran da trendli: yüzde 7'den 75'e çıkıp geri indi.

Sonuç: bir modelin ezberindeki "fiyat endeksinde log farkı al" kuralı
Türkiye verisinde yanlış cevap üretiyor. Genel geçer tarif burada
tutmuyor, testi fiilen çalıştırmak gerekiyor.

## Bunlardan çıkan kurallar

1. **Seviye serilerle korelasyon veya regresyon yok** — önce ADF.
   Sonuç durağan değilse rakam raporlanmadan önce uyarı çıkmalı.
2. **Fark derecesini varsayma, ölç.** I(1) varsayımı bu veride yanlış.
   Kaçıncı farkın durağan olduğu test edilip söylenmeli.
3. **Uygulanan dönüşüm çıktıda yazmalı.** "d2(TÜFE) ile d(FAİZ)
   arasında korelasyon 0.158" — hangi dönüşümle konuşulduğu görünmeli.
4. **Korelasyon nedensellik değil.** Kimlik stratejisi yoksa nedensel
   cümle kurulmamalı; Granger bile "nedensellik" demek için yetmez.
5. **Nokta tahmini değil aralık.** Tahmin döndüren her araç güven
   aralığı vermeli.

## Yapıldı

`analysis.py` ve iki yeni araç: `test_stationarity`, `analyze_relationship`.

Zorlama şöyle işliyor: **seviye korelasyonu hesaplayan bir araç yok.**
İki seriyi karşılaştırmanın tek yolu `analyze_relationship` ve o kendi
içinde durağanlık testini yapıyor. Model yanlış rakama ulaşamıyor, çünkü
o rakamı üreten bir yol açılmamış.

Aynı soruyu şimdi sorunca dönen cevap:

```
donusum            d2
korelasyon         0.0348
ham_seviye_kor.    0.8628  + "bu rakamı kullanma, sahte regresyon"
duraganlik         TÜFE I(2), FAİZ I(1)
uyarı              dereceler farklı, düşük dereceli seri aşırı farklanmış olabilir
yorum              korelasyondur, nedensellik değildir
```

Beş kuralın karşılıkları:

1. ADF testi araca gömülü, atlanamıyor
2. Fark derecesi ölçülüyor; I(2) çıkınca ayrıca uyarı veriliyor
3. `donusum` alanı her çıktıda var
4. `yorum` alanında nedensellik uyarısı sabit
5. Tahmin aracı henüz yok; eklendiğinde aralık zorunlu olacak (SONRA.md)

Ek olarak: iki seri de I(1) ise Engle-Granger eşbütünleşme testi
çalışıyor. Eşbütünleşme varsa sadece farklarla çalışmak uzun dönem
bilgisini atar, çıktı bunu söylüyor.

## Aracı kullanırken çıkan iki eksik

Metodoloji katmanı bittikten sonra aracı gerçek bir soruyla denedim:
kur geçişkenliği. İki eksik ortaya çıktı, ikisi de düzeltildi.

### Eksik 1: gecikme yok

USD/TRY ve TÜFE, aylık log farkı, 2010-2026:

```
gecikme 0 ay : +0.421
gecikme 1 ay : +0.568   <- tepe
gecikme 2 ay : +0.336
gecikme 3 ay : +0.208
...
gecikme 12 ay: -0.034
```

Kur geçişkenliği bir ay gecikmeyle en güçlü. Sadece eşanlı bakan bir
analiz ilişkiyi olduğundan zayıf gösteriyor. `max_lag` eklendi; tepe
eşanlı değilse çıktı bunu uyarı olarak söylüyor.

### Eksik 2: dereceler farklıysa aşırı farklama

USD/TRY I(1), TÜFE I(2). Araç ikisini de d2'ye zorlayınca korelasyon
0.155 çıkıyordu — sinyal farklamada eriyor. Oysa iktisadi olarak doğru
dönüşüm ikisi için de log farkı (yüzde değişim): 0.421.

`transform` parametresi eklendi. Dönüşüm elle verilebiliyor, ama seriyi
durağanlaştırmıyorsa araç bunu söylüyor:

```
TP.TUKFIY2025.GENEL: istenen dönüşüm (logd1) bu seriyi durağanlaştırmıyor
(ADF p=0.3512). Sonuç şişkin olabilir.
```

Susup uygulamak da, reddetmek de yanlış olurdu. Doğrusu uygulayıp
sorumluluğu görünür kılmak.

### Aynı sorunun üç cevabı

```
ham seviye korelasyonu     0.9856   <- model bunu söylerdi
otomatik dönüşüm (d2)      0.1546   <- aşırı farklanmış
logd1, gecikme 1           0.5685   <- doğru cevap
```

Üçü de aynı veriden çıkıyor. Aradaki farkı bilmek ekonometri bilmek
demek — aracın varlık sebebi bu.

Deney betikleri repoda yok, tek seferlikti; sayılar yukarıda.
