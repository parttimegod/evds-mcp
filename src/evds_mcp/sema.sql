-- EVDS depolama şeması. Depo.kur() bunu çalıştırır.
--
-- Tamamen idempotent: CREATE TABLE/INDEX IF NOT EXISTS. Var olan bir
-- kuruluma tekrar uygulamak zararsız -- yeniden dağıtımda ya da testte
-- her seferinde çağrılabilir.

CREATE TABLE IF NOT EXISTS seri (
    kod         TEXT PRIMARY KEY,
    ad          TEXT,
    ad_eng      TEXT,
    grup        TEXT,
    -- Frekans serinin özelliği, satırın değil -- bu yüzden aşağıdaki
    -- gozlem tablosunda tüm frekanslar bir arada duruyor, frekans başına
    -- ayrı tablo yok. Ayrı tablo olsaydı çok-serili bir sorgu (farklı
    -- frekanslardan iki seriyi karşılaştırmak gibi) union'a dönerdi.
    frekans     SMALLINT,
    kaynak      TEXT,
    baslangic   DATE,
    bitis       DATE,
    guncelleme  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS gozlem (
    kod       TEXT NOT NULL REFERENCES seri(kod) ON DELETE CASCADE,
    tarih     DATE NOT NULL,
    -- NULL'a izin veriliyor: eksik bir gözlem sıfır demek değil. EVDS,
    -- bir serinin henüz yayınlanmadığı dönemler için null döner (bkz.
    -- client.py). Burada 0 saklarsak her ortalama ve her fark sessizce
    -- bozulur -- sıfır gerçek bir değer gibi hesaba girer.
    deger     DOUBLE PRECISION,
    cekilme   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Doğal anahtar (kod, tarih): yeniden çekmeyi ON CONFLICT ... DO
    -- UPDATE ile idempotent yapıyor, ve mükerrer bir gözlemi "pek
    -- olası değil" değil "imkansız" kılıyor.
    PRIMARY KEY (kod, tarih)
);

-- Baskın sorgu "bu serinin son N gözlemi" (bkz. Depo.son_gozlemler).
-- Azalan sırada indeks bu sorguyu sort'suz bir indeks taramasına
-- çeviriyor; (kod, tarih) artan sırada olsaydı LIMIT'ten önce ayrıca
-- ters çevirmek gerekirdi.
CREATE INDEX IF NOT EXISTS gozlem_kod_tarih_desc_idx ON gozlem (kod, tarih DESC);
