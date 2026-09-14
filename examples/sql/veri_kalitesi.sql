-- NULL değerler eksik EVDS gözlemleridir, sıfır değil -- bkz. sema.sql'de
-- gozlem.deger yorumu. Bir serinin ne kadarının dolu olduğunu görmek için:
SELECT
    s.kod,
    count(g.*) AS satir_sayisi,
    count(*) FILTER (WHERE g.deger IS NULL) AS null_sayisi
FROM seri AS s
LEFT JOIN gozlem AS g ON g.kod = s.kod
GROUP BY s.kod
ORDER BY s.kod;

-- LAG "bir önceki KAYITLI SATIR" demek, "bir önceki TAKVİM DÖNEMİ"
-- değil -- bir dönem hiç satır olarak yoksa (NULL değil, satırın kendisi
-- eksikse) bu sessizce yanlış bir dönemi "önceki" diye etiketler (bkz.
-- Depo.gecikmeli_oku'nun docstring'i). NULLIF(..., 0) ise sıfıra bölmeyi
-- hataya değil NULL'a çeviriyor -- bir önceki değer tam olarak 0 ise
-- yüzde değişim tanımsızdır, hata fırlatmak yerine NULL dönmek daha
-- doğru.
SELECT
    tarih,
    deger,
    LAG(deger) OVER (ORDER BY tarih) AS onceki_satir,
    100.0 * (deger - LAG(deger) OVER (ORDER BY tarih))
        / NULLIF(abs(LAG(deger) OVER (ORDER BY tarih)), 0) AS yuzde_degisim
FROM gozlem
WHERE kod = 'TP.FG.J0'
ORDER BY tarih;

-- Bunun yerine gerçek bir önceki TAKVİM ayını isteyen bir self-join.
-- Sabit bir INTERVAL ile kaydırma yalnızca dönemleri arasında sabit bir
-- takvim aralığı olan frekanslarda güvenli (aylık, çeyreklik, altı
-- aylık, yıllık, günlük) -- işgünü ya da belirli bir güne sabitlenmiş
-- haftalık serilerde resmi tatiller bu kaymayı bozar (bkz.
-- Depo._takvim_araligi). Burada tek bir sabit gecikme noktasını
-- gösteriyor; bir serinin TÜM boşluklarını açığa çıkarmak için
-- Depo.takvim_gecikmeli_oku'nun generate_series tabanlı izgarasını
-- kullanın.
SELECT
    bu_ay.tarih,
    bu_ay.deger,
    onceki_ay.deger AS onceki_takvim_ayi
FROM gozlem AS bu_ay
LEFT JOIN gozlem AS onceki_ay
  ON onceki_ay.kod = bu_ay.kod
 AND onceki_ay.tarih = bu_ay.tarih - INTERVAL '1 month'
WHERE bu_ay.kod = 'TP.FG.J0'
ORDER BY bu_ay.tarih;
