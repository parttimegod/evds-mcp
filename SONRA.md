# Açık işler

## Veri ve arama

- Katalog önbelleği, her başlangıçta aynı veriyi çekmeyi azaltabilir.
- Eşit arama puanında kısa adı tercih etmek zayıf bir kural; ulusal ve
  bölgesel serilerle sıralama örnekleri gerekiyor.
- Arşiv tespiti ad içindeki etikete bakıyor. Kapsam tarihleriyle birlikte
  değerlendirilmesi daha uygun olabilir.
- Frekans kodları canlı API ile daha geniş sınanmalı. İşgünü ve haftalık
  serilerin tatil kaymalarına özel takvim gerekir.

## Analiz

- MCP analizindeki eksik gözlemler atılıyor. Fark ve gecikmenin takvimde
  birden fazla dönemi aşmasını önleyen bir veri hazırlama yolu gerekiyor.
- Sabit terimli ADF tek seçenek. Trendli test, KPSS ve kırılma kontrolleri
  sonuçları karşılaştırmak için eklenebilir.
- Gecikme tepesi aynı örneklemde seçiliyor. Yeni veri üzerinde doğrulama
  ve çoklu karşılaştırma değerlendirmesi yapılmıyor.
- Fark dereceleri ayrı serilerde farklı olabilir. Ortak en yüksek derece
  yerine açıkça seçilmiş alternatif modeller karşılaştırılabilir.
- Bir tahmin aracı eklenirse hata aralıkları ve zaman sıralı doğrulama
  birlikte tasarlanmalı.

## PostgreSQL

- Gözlem tablosu son değeri tutuyor; revizyonların eski değerleri yok.
  Tam revizyon geçmişi ayrı bir tablo ve kullanım kararı gerektirir.
- EVDS istemcisi sayıları önce float'a çeviriyor. API metnindeki bütün
  basamakları korumak için dönüşüm istemci tarafında ele alınmalı.
- Eski kurulumlarda yinelenen DESC indeks kalabilir. Ölçülmüş bir
  geçiş gereksinimi oluşursa ayrı bir migration hazırlanabilir.

PyPI yayını ve ek veri kaynakları bu işlerin ardından değerlendirilebilir.
