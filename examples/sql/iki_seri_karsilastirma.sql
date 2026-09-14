-- İki seriyi yalnızca ikisinin de değeri olduğu tarihlerde karşılaştırır.
-- Kodları kendi serilerinizle değiştirin; iki seri farklı frekanstaysa
-- (ör. biri aylık biri günlük) tarih sütunu birebir eşleşmez, bu sorgu
-- aynı frekanstaki -- ya da tesadüfen aynı takvim günlerine denk gelen --
-- iki seri için anlamlıdır.
SELECT
    a.tarih,
    a.deger AS tufe,
    b.deger AS usd_try
FROM gozlem AS a
JOIN gozlem AS b
  ON b.tarih = a.tarih
WHERE a.kod = 'TP.FG.J0'
  AND b.kod = 'TP.DK.USD.A.YTL'
  AND a.deger IS NOT NULL
  AND b.deger IS NOT NULL
ORDER BY a.tarih;
