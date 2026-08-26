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

## Sıradaki iş

Bu kuralları öneri olarak değil, araç seviyesinde **zorunluluk** olarak
kodlamak. Model durağanlık testinden geçmeden regresyon aracını
çağıramamalı.

Deney betiği repoda yok, tek seferlikti; sayılar yukarıda.
