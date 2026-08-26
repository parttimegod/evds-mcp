# Sonra

Aklıma gelen ama şimdi yapmayacağım şeyler. İlk sürüm çıkana kadar
buraya yazıp geçiyorum, yoksa hiç bitmeyecek.

## Arama
- Şu an puanlı keyword eşleşmesi. Anlamsal aramaya geçilebilir —
  yerel embedding modeli var, katalog zaten küçük.
- Sıralama ince ayarı: "enflasyon" sorgusunda İstanbul TÜFE'si ulusal
  TÜFE'nin önüne geçiyor, çünkü eşit puanda kısa adı seçiyoruz. Ad
  uzunluğu zayıf bir ölçüt.
- Arşiv tespitini ada bakarak yapıyoruz ("(Arşiv)" geçiyor mu). END_DATE
  eski mi diye bakmak çok daha sağlam olur -- alan zaten künyede.
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
- serieList künyesinde METADATA_LINK ve REV_POL_LINK alanları var,
  çoğu null geliyor. Dolu olanları künyeye ekle.
- datagroups mode=1 ve mode=2 ne işe yarıyor? mode=2&code=10 boş döndü,
  mode=0 tamamını veriyor. Kategoriye göre filtreleme başka türlü olmalı.

## Aşama 2
Durağanlık zorunluluğu ve sahte regresyon uyarısı yapıldı (ASAMA2.md).
Kalanlar:
- Tahmin aracı. Eklenirse güven aralığı zorunlu olmalı, nokta tahmini
  dönmemeli.
- Artık teşhisleri: regresyon aracı eklenirse Durbin-Watson, Breusch-Godfrey.
- Yapısal kırılma testi. ADF kırılmayı birim kök sanıyor; şu an
  "durağanlaşmadı" deyip geçiyoruz, Zivot-Andrews daha doğru olur.
- Mevsimsellik. Aylık serilerde mevsimsel birim kök (HEGY) bakılmıyor.

## Ambalaj
- PyPI'ya yükleme
- README'ye örnek oturum kaydı (asciinema?)
- CI
