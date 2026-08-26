# Sonra

Aklıma gelen ama şimdi yapmayacağım şeyler. İlk sürüm çıkana kadar
buraya yazıp geçiyorum, yoksa hiç bitmeyecek.

## Arama
- Şu an düz keyword eşleşmesi. Anlamsal aramaya geçilebilir —
  yerel embedding modeli var, katalog zaten küçük.
- Eşanlamlı sözlüğü: "enflasyon" -> TÜFE, ÜFE. "faiz" -> politika faizi,
  gecelik, ağırlıklı ortalama fonlama.
- Kısaltmalar: TÜFE/tufe/CPI hepsi aynı yere gitmeli.

## Veri
- Katalog önbelleği. Şu an her açılışta çekiyor.
- TÜİK. Ayrı API, ayrı dert.
- BDDK, TÜİK bölgesel seriler.
- Frekans dönüşümü (aylıktan çeyreğe toplama).

## Doğrulama
- Frekans kodlarının tamamını API'ye karşı doğrula. Şu an sadece
  5 = aylık'tan eminim, gerisi dokümandan.
- Revizyon tarihi alanı geliyor mu, geliyorsa künyeye ekle.

## Aşama 2 (asıl iş)
- Durağanlık testi zorunluluğu
- Sahte regresyon uyarısı
- Artık teşhisleri
- Güven aralığı olmadan tahmin döndürme

## Ambalaj
- PyPI'ya yükleme
- README'ye örnek oturum kaydı (asciinema?)
- CI
