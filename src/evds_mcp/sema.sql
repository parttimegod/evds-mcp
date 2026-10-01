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

-- Bir EVDS çekiminin denetim kaydı: hangi seri, ne zaman, hangi aralık
-- istendi, kaç gözlem/kaç null döndü. Aşağıdaki gozlem.cekim_id buraya
-- işaret ediyor -- "bu sayı nereden geldi, ne zaman çekildi" sorusunun
-- cevabı satır satır burada. Revize edilen makro serilerde (TCMB/TÜİK
-- bir dönemi sonradan düzeltebiliyor) provenance lüks değil: hangi
-- çekimin hangi değeri yazdığını ayırt etmenin tek yolu bu tablo.
CREATE TABLE IF NOT EXISTS cekim (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kod                TEXT NOT NULL REFERENCES seri(kod) ON DELETE CASCADE,
    istenen_baslangic  DATE NOT NULL,
    istenen_bitis      DATE NOT NULL,
    cekilme            TIMESTAMPTZ NOT NULL DEFAULT now(),
    gozlem_sayisi      INTEGER NOT NULL,
    null_sayisi        INTEGER NOT NULL,
    -- İstenen aralığın ters olması (baslangic > bitis) çağıran taraftaki
    -- bir hatanın işareti; veritabanı seviyesinde de imkansız kılıyoruz.
    CHECK (istenen_baslangic <= istenen_bitis)
);

-- Bir serinin istenen tarih aralığına göre çekimlerini daraltmak için.
CREATE INDEX IF NOT EXISTS cekim_kod_aralik_idx
    ON cekim (kod, istenen_baslangic, istenen_bitis);

CREATE TABLE IF NOT EXISTS gozlem (
    kod       TEXT NOT NULL REFERENCES seri(kod) ON DELETE CASCADE,
    tarih     DATE NOT NULL,
    -- EVDS'nin ham Tarih alanı, örn. "2020-3" ya da "01-01-2020" --
    -- biçim frekansa göre değişiyor ve client.py'nin belirttiği gibi
    -- şu an yalnızca aylık için canlı doğrulandı (bkz. SONRA.md).
    -- Aylık etiket ayın ilk gününe çevriliyor; günlük tarih korunuyor
    -- (bkz. depo._gozlem_tarihi). Bu normalizasyon yanlış
    -- çıkarsa ham_donem, orijinal metni geri getirip elle teşhis
    -- etmeyi mümkün kılıyor -- parse hatası sessizce kaybolmuyor.
    ham_donem TEXT NOT NULL,
    -- NULL'a izin veriliyor: eksik bir gözlem sıfır demek değil. EVDS,
    -- bir serinin henüz yayınlanmadığı dönemler için null döner (bkz.
    -- client.py). Burada 0 saklarsak her ortalama ve her fark sessizce
    -- bozulur -- sıfır gerçek bir değer gibi hesaba girer.
    --
    -- Depoda ondalık aritmetik için NUMERIC. İstemci değerleri önce
    -- float'a çeviriyor; kaynak metnin tüm hassasiyetini korumaz.
    -- Depo'ya doğrudan Decimal verilirse bu ara dönüşüm yapılmaz.
    deger     NUMERIC,
    -- Bu değeri en son hangi çekim yazdı. ON DELETE SET NULL: bir
    -- cekim kaydı silinirse (ör. eski denetim kayıtlarının temizliği)
    -- gözlem satırı kaybolmaz, sadece provenance'ı boşa düşer.
    cekim_id  BIGINT REFERENCES cekim(id) ON DELETE SET NULL,
    -- Doğal anahtar (kod, tarih): yeniden çekmeyi ON CONFLICT ... DO
    -- UPDATE ile idempotent yapıyor, ve mükerrer bir gözlemi "pek
    -- olası değil" değil "imkansız" kılıyor.
    PRIMARY KEY (kod, tarih)
);

-- WHERE kod = ... ORDER BY tarih DESC LIMIT ... sorgusu birincil
-- anahtarın ters taramasını kullanır; ayrıca DESC indeksi gerekmez.
