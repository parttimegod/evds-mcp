"""EVDS verisi için opsiyonel PostgreSQL depolama katmanı.

İki amacı var: aynı seriyi tekrar tekrar EVDS'den çekmemek (istek sayısı
sınırlı ve yavaş), ve geçmiş veriyi SQL ile sorgulayabilmek -- client.py
tek seferlik istek/yanıt veriyor, geçmişe dönük analiz için bir yer yok.

Bu katman tamamen opsiyonel: psycopg pyproject.toml'da `depo` ekstrası
altında, ana paket PostgreSQL kurulu olmadan da çalışmaya devam ediyor.
Bu yüzden psycopg modül yüklenirken değil, ilk gerçek kullanımda
içeri alınıyor -- `import evds_mcp` psycopg'siz bir makinede patlamamalı.

Şema üç tablo: seri (künye), cekim (her EVDS çekiminin denetim kaydı) ve
gozlem (değerler, en son hangi çekimin yazdığına referans veriyor),
sema.sql'de. Tasarım kararları orada satır satır yorumlanmış durumda.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from .client import Gozlem
from .text import arama_anahtari

if TYPE_CHECKING:
    from .catalog import SeriKunye

_SEMA_YOLU = Path(__file__).parent / "sema.sql"


class DepoHatasi(Exception):
    pass


@dataclass(frozen=True)
class DepoGozlem:
    tarih: date
    deger: Decimal | None
    ham_donem: str


@dataclass(frozen=True)
class GecikmeliGozlem:
    tarih: date
    deger: Decimal | None
    onceki: Decimal | None  # `gecikme` dönem önceki değer; yoksa None


@dataclass(frozen=True)
class CekimKaydi:
    id: int
    istenen_baslangic: date
    istenen_bitis: date
    cekilme: datetime
    gozlem_sayisi: int
    null_sayisi: int


def _psycopg():
    try:
        import psycopg
    except ImportError as exc:
        raise DepoHatasi(
            "PostgreSQL desteği kurulu değil. `uv sync --extra depo` ile kur "
            "(psycopg[binary] paketini ekler)."
        ) from exc
    return psycopg


def _tarih_oku(metin: str | None) -> date | None:
    """SeriKunye'nin GG-AA-YYYY künye tarihini date'e çevirir.

    EVDS künyede tarihi client._tarih_yaz ile aynı biçimde veriyor. Boş
    string bazı serilerde kapsam bilgisinin gelmediği anlamına geliyor;
    sahte bir tarih uydurmak yerine None saklıyoruz.
    """
    if not metin:
        return None
    try:
        return datetime.strptime(metin, "%d-%m-%Y").date()
    except ValueError as exc:
        raise DepoHatasi(f"Bilinmeyen künye tarihi biçimi: {metin!r}") from exc


_AY_DESENI = re.compile(r"^(\d{4})-(\d{1,2})$")


def _gozlem_tarihi(metin: str) -> date:
    """Bir gözlemin Tarih alanını date'e çevirir.

    client.py'nin belirttiği gibi EVDS'nin Tarih biçimi frekansa göre
    değişiyor; canlı doğrulanan tek biçim aylık için "YYYY-M" (örn.
    "2020-1"), ayın ilk günü olarak saklanıyor. Diğer frekanslar için
    dokümandaki GG-AA-YYYY biçimi de deneniyor. İkisi de tutmazsa
    sessizce yanlış bir tarih saklamak yerine hata veriyoruz. Ham metnin
    kendisi ayrıca gozlem.ham_donem'e de yazılıyor -- burada bir parse
    hatası olursa orijinal değer kaybolmuyor.
    """
    eslesme = _AY_DESENI.match(metin)
    if eslesme:
        yil, ay = int(eslesme.group(1)), int(eslesme.group(2))
        return date(yil, ay, 1)
    try:
        return datetime.strptime(metin, "%d-%m-%Y").date()
    except ValueError:
        raise DepoHatasi(f"Bilinmeyen gözlem tarihi biçimi: {metin!r}") from None


# client.FREKANS'taki 1-8 kodlarıyla aynı sayım; EVDS'nin serbest metin
# FREQUENCY_STR'ından ("AYLIK", "HAFTALIK(CUMA)", "ÜÇ AYLIK" gibi) bu
# kodlara geçiş burada.
def _frekans_kodu(metin: str) -> int:
    """SeriKunye.frekans'taki ekran metnini şemadaki SMALLINT koduna çevirir.

    EVDS bunu sorgu parametresi değil, ekranda gösterilecek serbest metin
    olarak veriyor (haftanın günü parantez içinde, çeyreklik "ÜÇ AYLIK"
    yazıyor gibi) -- client.FREKANS sözlüğüyle birebir eşleşmiyor. Bu
    yüzden anahtar kelimeyle eşleştiriyoruz, ayrım gücü yüksekten düşüğe:
    "ÜÇ AYLIK" ve "ALTI AYLIK" da içlerinde "aylık" geçiriyor, önce onlar
    elenmezse hepsi yanlışlıkla aylık (5) olarak sayılır.
    """
    m = arama_anahtari(metin)
    if "is gun" in m:
        return 2
    if "gunluk" in m:
        return 1
    if "haftalik" in m:
        return 3
    if "ayda" in m:
        return 4
    if "uc aylik" in m or "ceyrek" in m:
        return 6
    if "alti aylik" in m or "6 aylik" in m:
        return 7
    if "aylik" in m:
        return 5
    if "yillik" in m:
        return 8
    raise DepoHatasi(f"Bilinmeyen frekans metni: {metin!r}")


# client.FREKANS koduna göre generate_series'e verilecek takvim adımı.
# Yalnızca "her dönem takvimde sabit bir aralıkta gelir" garantisi olan
# frekanslar burada -- bkz. _takvim_araligi'ndaki gerekçe.
_TAKVIM_ARALIKLARI: dict[int, str] = {
    1: "1 day",  # günlük
    5: "1 month",  # aylık
    6: "3 months",  # çeyreklik / üç aylık
    7: "6 months",  # altı aylık
    8: "1 year",  # yıllık
}

# salt_okunur_sorgu'nun kabul ettiği tek statement türleri. str.startswith
# bir tuple alabildiği için tek çağrıda hepsi kontrol ediliyor.
_SALT_OKUNUR_BASLANGIC = ("select", "with", "show", "explain")

# Bu frekanslar kasıtlı olarak _TAKVIM_ARALIKLARI'nda yok -- sabit bir
# takvim adımı varsaymak yanlış bir izgarayı sessizce üretir. Neden
# burada, _takvim_araligi'nin fırlattığı hatada tekrarlanıyor.
_TAKVIMSIZ_FREKANSLAR: dict[int, str] = {
    2: (
        "işgünü: resmi tatiller yıldan yıla değişiyor, sabit bir gün "
        "sayısıyla hesaplanamaz"
    ),
    3: (
        "haftalık: EVDS'de çoğu zaman belirli bir güne sabit (ör. "
        "'HAFTALIK(CUMA)') ama o gün resmi tatilse gözlem başka bir güne "
        "kayabiliyor -- sabit 7 günlük adım bu kaymada yanlış hizalanır"
    ),
    4: (
        "ayda2 (yarı aylık): EVDS'nin bu frekansta ayın hangi iki gününü "
        "kullandığı doğrulanmış değil -- SONRA.md'nin belirttiği gibi "
        "frekans kodlarından canlı doğrulanan tek biçim aylık (5); "
        "tahmin etmek yanlış bir izgarayı sessizce üretme riski taşır"
    ),
}


def _takvim_araligi(frekans_kodu: int) -> str:
    """Frekans koduna karşılık gelen generate_series adımını döner.

    Sadece dönemleri arasında sabit ve tahmin edilebilir bir takvim
    aralığı olan frekanslar burada eşleniyor. Geri kalanı (işgünü,
    haftalık, ayda2) için DepoHatasi fırlatılır -- bkz.
    _TAKVIMSIZ_FREKANSLAR. Bilinmeyen bir kod da aynı şekilde hata verir.
    """
    if frekans_kodu in _TAKVIM_ARALIKLARI:
        return _TAKVIM_ARALIKLARI[frekans_kodu]
    sebep = _TAKVIMSIZ_FREKANSLAR.get(frekans_kodu, "bilinmeyen frekans kodu")
    raise DepoHatasi(
        f"Takvim tabanlı gecikme frekans kodu {frekans_kodu} için "
        f"desteklenmiyor: {sebep}. Bunun yerine satır tabanlı "
        "gecikmeli_oku kullanın (farkı için o metodun docstring'ine bakın)."
    )


class Depo:
    """PostgreSQL bağlantısını yöneten, şemayı uygulayan depolama katmanı.

    Her metot kendi bağlantısını açıp kapatıyor -- bağlantı havuzu ya da
    uzun ömürlü bir bağlantı yok. Bu basit ve bağlantı yaşam döngüsüyle
    uğraşmayı gerektirmiyor; çok sayıda gözlemi tek seferde yazmak
    isteyen çağıran zaten gozlem_yaz'a toplu liste veriyor.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _baglan(self):
        return _psycopg().connect(self._dsn)

    def kur(self) -> None:
        """Şemayı idempotent olarak uygular (bkz. sema.sql)."""
        sql = _SEMA_YOLU.read_text(encoding="utf-8")
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(sql)

    def seri_yaz(self, kunye: SeriKunye) -> None:
        """Bir serinin künyesini yazar; varsa günceller (ON CONFLICT)."""
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                INSERT INTO seri (kod, ad, ad_eng, grup, frekans, kaynak,
                                   baslangic, bitis, guncelleme)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (kod) DO UPDATE SET
                    ad = EXCLUDED.ad,
                    ad_eng = EXCLUDED.ad_eng,
                    grup = EXCLUDED.grup,
                    frekans = EXCLUDED.frekans,
                    kaynak = EXCLUDED.kaynak,
                    baslangic = EXCLUDED.baslangic,
                    bitis = EXCLUDED.bitis,
                    guncelleme = now()
                """,
                (
                    kunye.kod,
                    kunye.ad,
                    kunye.ad_eng,
                    kunye.grup_kodu,
                    _frekans_kodu(kunye.frekans),
                    kunye.kaynak,
                    _tarih_oku(kunye.baslangic),
                    _tarih_oku(kunye.bitis),
                ),
            )

    def gozlem_yaz(
        self, kod: str, baslangic: date, bitis: date, gozlemler: list[Gozlem]
    ) -> int:
        """Bir EVDS çekimini kaydeder: cekim denetim satırı + gozlem upsert,
        tek işlemde. Yazılan gözlem satırı sayısını döner.

        baslangic/bitis burada EVDS'ten FİİLEN İSTENEN aralık --
        client.EVDS.veri çağrısına verilen start/end -- gözlemlerin fiilen
        kapsadığı aralık değil. İkisi ayrışabilir: EVDS bir dönemi henüz
        yayınlamamışsa o dönem hiç satır olarak dönmez, ama siz yine de o
        aralığı istemiş oluyorsunuz. cekim tablosunun "ne istendi"
        sorusuna EVDS'e giden gerçek çağrıyla birebir cevap vermesi için
        bu ayrım korunuyor; gözlem sayısından ya da min/max tarihten geri
        türetilmiyor.

        executemany kullanıyoruz, COPY değil. COPY sadece ekleme yapıyor;
        burada gereken idempotent upsert (ON CONFLICT DO UPDATE) COPY ile
        doğrudan olmuyor, bir staging tabloya kopyalayıp sonra ayrı bir
        merge adımı gerektirirdi. Tek bir EVDS isteği tipik olarak onlarca
        ile birkaç bin gözlem döndürüyor (bkz. client.py) -- bu ölçekte
        executemany'nin ek karmaşıklık gerektirmemesi, COPY'nin hız
        kazancından daha değerli.
        """
        if baslangic > bitis:
            raise DepoHatasi(f"İstenen başlangıç bitişten sonra: {baslangic} > {bitis}")
        satirlar = [
            (kod, _gozlem_tarihi(g.tarih), g.tarih, g.deger) for g in gozlemler
        ]
        null_sayisi = sum(1 for g in gozlemler if g.deger is None)
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                INSERT INTO cekim (kod, istenen_baslangic, istenen_bitis,
                                    gozlem_sayisi, null_sayisi)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (kod, baslangic, bitis, len(satirlar), null_sayisi),
            )
            (cekim_id,) = imlec.fetchone()
            if satirlar:
                imlec.executemany(
                    """
                    INSERT INTO gozlem (kod, tarih, ham_donem, deger, cekim_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (kod, tarih) DO UPDATE SET
                        ham_donem = EXCLUDED.ham_donem,
                        deger = EXCLUDED.deger,
                        cekim_id = EXCLUDED.cekim_id
                    """,
                    [(*satir, cekim_id) for satir in satirlar],
                )
        return len(satirlar)

    def cekimler_oku(self, kod: str) -> list[CekimKaydi]:
        """Bir serinin çekim geçmişini en yeniden en eskiye döner.

        Provenance sorgusu: "bu değer ne zaman, hangi aralık istenerek
        çekildi, kaç gözlem/kaç null döndü" sorusunun cevabı burada --
        bkz. sema.sql'deki cekim tablosu yorumu.
        """
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                SELECT id, istenen_baslangic, istenen_bitis, cekilme,
                       gozlem_sayisi, null_sayisi
                FROM cekim
                WHERE kod = %s
                ORDER BY cekilme DESC
                """,
                (kod,),
            )
            return [
                CekimKaydi(
                    id=i,
                    istenen_baslangic=ib,
                    istenen_bitis=ie,
                    cekilme=c,
                    gozlem_sayisi=gs,
                    null_sayisi=ns,
                )
                for i, ib, ie, c, gs, ns in imlec.fetchall()
            ]

    def gozlem_oku(self, kod: str, baslangic: date, bitis: date) -> list[DepoGozlem]:
        """[baslangic, bitis] aralığındaki gözlemleri tarihe göre artan döner."""
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                SELECT tarih, deger, ham_donem FROM gozlem
                WHERE kod = %s AND tarih BETWEEN %s AND %s
                ORDER BY tarih
                """,
                (kod, baslangic, bitis),
            )
            return [
                DepoGozlem(tarih=t, deger=d, ham_donem=h)
                for t, d, h in imlec.fetchall()
            ]

    def son_gozlemler(self, kod: str, adet: int) -> list[DepoGozlem]:
        """Son `adet` gözlemi en yeniden en eskiye döner.

        gozlem_kod_tarih_desc_idx bu ORDER BY + LIMIT'i sort'suz bir
        indeks taramasına çeviriyor.
        """
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                SELECT tarih, deger, ham_donem FROM gozlem
                WHERE kod = %s
                ORDER BY tarih DESC
                LIMIT %s
                """,
                (kod, adet),
            )
            return [
                DepoGozlem(tarih=t, deger=d, ham_donem=h)
                for t, d, h in imlec.fetchall()
            ]

    def gecikmeli_oku(self, kod: str, gecikme: int) -> list[GecikmeliGozlem]:
        """Her gözlemi `gecikme` KAYITLI SATIR önceki değeriyle birlikte döner.

        DİKKAT -- bu satır tabanlı bir LAG: pencere var olan gozlem
        satırlarına göre kayar, takvime göre değil. LAG(deger, n) OVER
        (ORDER BY tarih) n'inci ÖNCEKİ SATIRI döner, n dönem önceki
        TARİHİ değil. Bir dönem hiç satır olarak yoksa (NULL değer değil,
        satırın kendisi eksik -- ör. EVDS o dönemi hiç döndürmediyse ya da
        aralığın bir kısmı hiç çekilmediyse), LAG o boşluğu fark etmeden
        atlar: n=1 istendiğinde aslında 2 takvim dönemi önceki değer
        dönmüş olur ama "1 dönem önce" diye etiketlenir. Makro serilerde
        boşluk sık olduğundan bu, gecikmeli korelasyonu sessizce
        bozabilecek türden bir hata.

        Boşluksuz bir seride (her dönem gerçekten bir satır olarak var,
        değeri NULL bile olsa) bu metot doğru ve daha hızlıdır --
        takvim_gecikmeli_oku'nun generate_series/LEFT JOIN maliyeti yok.
        Boşluk olabilecek bir seride (EVDS'nin aralığın bir kısmını hiç
        döndürmediği, ya da yerel depoya henüz tüm aralığın çekilmediği
        durumlar) onun yerine takvim_gecikmeli_oku kullanın.

        LAG penceresi (kod, tarih) sırasına göre kaydırma yapıyor; WHERE
        zaten tek bir kod'a daralttığı için PARTITION BY burada işlevsel
        olarak gereksiz, ama sorguyu doğru tutuyor -- WHERE bir gün
        birden çok koda gevşetilirse (ör. IN (...)) pencereler serilere
        karışmadan ayrı kalır. İlk `gecikme` satırda önceki değer yok,
        LAG bunu doğal olarak NULL döner.
        """
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                SELECT tarih, deger,
                       LAG(deger, %s) OVER (PARTITION BY kod ORDER BY tarih) AS onceki
                FROM gozlem
                WHERE kod = %s
                ORDER BY tarih
                """,
                (gecikme, kod),
            )
            return [
                GecikmeliGozlem(tarih=t, deger=d, onceki=o)
                for t, d, o in imlec.fetchall()
            ]

    def takvim_gecikmeli_oku(self, kod: str, gecikme: int) -> list[GecikmeliGozlem]:
        """Her gözlemi `gecikme` TAKVİM DÖNEMİ önceki değeriyle birlikte döner.

        gecikmeli_oku'nun aksine (bkz. onun docstring'i, orada anlatılan
        hatanın burada nasıl önlendiği aşağıda) önce seri.frekans'tan bu
        serinin dönemleri arasındaki beklenen takvim aralığını çıkarıyoruz
        (_takvim_araligi: günlük->1 gün, aylık->1 ay, çeyreklik->3 ay,
        altı aylık->6 ay, yıllık->1 yıl), generate_series ile bu aralıkta
        tam bir takvim izgarası kuruyoruz, ve gozlem'i bu izgaraya
        LEFT JOIN ediyoruz. Eksik bir dönem artık açıkça NULL değerli bir
        satır oluyor -- satırın kendisi eksik değil -- bu yüzden
        LAG(deger, n) izgara üzerinde çalışınca "n dönem önce" ifadesi
        şansa değil kurguya dayanarak doğru çıkıyor: n. önceki satır,
        tanım gereği n. önceki takvim dönemidir.

        Takvim sınırları (min/max tarih) seri.baslangic/bitis'ten değil,
        bu kod için yerelde depolanmış gozlem satırlarının kendisinden
        alınıyor. Amaç EVDS'nin serinin tüm hayatı boyunca ne
        yayınlaması gerektiğini modellemek değil, yerelde depolanan
        aralık içinde bir dönemin sessizce atlanıp atlanmadığını tespit
        etmek -- seri.baslangic öncesi ya da henüz çekilmemiş bir kuyruk
        "boşluk" değil, "henüz istenmemiş" demek.

        Bedeli: iki ekstra alt sorgu (min/max tarih) + generate_series +
        LEFT JOIN -- gecikmeli_oku'dan daha yavaş. Boşluksuz bir seride
        iki metot aynı sonucu verir; fark yalnızca boşluklu serilerde
        ortaya çıkar.

        Şu frekanslar için takvim aralığı güvenilir şekilde
        belirlenemediğinden DepoHatasi fırlatılır (bkz. _takvim_araligi
        ve _TAKVIMSIZ_FREKANSLAR): işgünü (resmi tatiller yıldan yıla
        değişiyor, sabit adım yok), haftalık (belirli bir güne sabitse
        -- ör. CUMA -- o gün tatilse gözlem kayabiliyor, sabit 7 günlük
        adım bunu yanlış hizalar), ayda2/yarı aylık (EVDS'nin bu
        frekansta ayın hangi iki gününü kullandığı doğrulanmış değil).
        Bu üçünde tahmin etmek yerine hata vermeyi seçtik: sessizce
        yanlış bir izgara üretmek, hiç izgare üretmemekten daha kötü.
        """
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute("SELECT frekans FROM seri WHERE kod = %s", (kod,))
            satir = imlec.fetchone()
            if satir is None or satir[0] is None:
                raise DepoHatasi(
                    f"{kod!r} için frekans bilgisi yok; önce seri_yaz çağırın."
                )
            araligi = _takvim_araligi(satir[0])
            imlec.execute(
                """
                WITH takvim AS (
                    SELECT gs::date AS tarih
                    FROM generate_series(
                        (SELECT min(tarih) FROM gozlem WHERE kod = %(kod)s),
                        (SELECT max(tarih) FROM gozlem WHERE kod = %(kod)s),
                        %(aralik)s::interval
                    ) AS gs
                ),
                izgara AS (
                    SELECT t.tarih, g.deger
                    FROM takvim t
                    LEFT JOIN gozlem g
                        ON g.kod = %(kod)s AND g.tarih = t.tarih
                )
                SELECT tarih, deger,
                       LAG(deger, %(gecikme)s) OVER (ORDER BY tarih) AS onceki
                FROM izgara
                ORDER BY tarih
                """,
                {"kod": kod, "aralik": araligi, "gecikme": gecikme},
            )
            return [
                GecikmeliGozlem(tarih=t, deger=d, onceki=o)
                for t, d, o in imlec.fetchall()
            ]

    def salt_okunur_sorgu(
        self, sql: str, limit: int = 200, zaman_asimi_ms: int = 5000
    ) -> list[dict]:
        """Tek bir salt-okunur SQL ifadesini çalıştırır, satırları sözlük
        listesi olarak döner.

        Bu, stash'te kalan postgres_cli.py'nin `query` komutundan ve
        readonly_query'sinden Türkçeleştirilerek buraya taşındı: modülün
        kendi amacına ("geçmiş veriyi SQL ile sorgulayabilmek", bkz.
        modül docstring'i) doğrudan hizmet eden, genel amaçlı ve
        güvenlik açısından dikkatli bir sorgu yürütücüsü. postgres_cli.py'nin
        geri kalanı (sync-group/fetch/coverage komutları, ayrı bir CLI
        script'i) taşınmadı -- bkz. README'deki gerekçe.

        Kabul edilen TEK ifade SELECT, WITH, SHOW ya da EXPLAIN ile
        başlamalı, noktalı virgülle ayrılmış ikinci bir ifade
        içermemeli. transaction_read_only=on altında ve bir
        statement_timeout ile, prepared execution kullanarak çalıştırılır
        (prepared execution + tek-ifade kontrolü COMMIT/SET gibi bir
        kaçış zincirini engelliyor). Bu bir güvenlik sandbox'ı DEĞİL --
        salt-okunur bir yürütme katmanı. Yalnızca güvendiğiniz SQL'i
        buradan çalıştırın.
        """
        ifade = sql.strip()
        if ifade.endswith(";"):
            ifade = ifade[:-1].rstrip()
        if not ifade.lower().startswith(_SALT_OKUNUR_BASLANGIC):
            raise DepoHatasi(
                "Yalnızca SELECT, WITH, SHOW ve EXPLAIN ifadeleri kabul edilir."
            )
        if ";" in ifade:
            raise DepoHatasi("Yalnızca tek bir SQL ifadesi kabul edilir.")
        if not 1 <= limit <= 1000:
            raise DepoHatasi("limit 1 ile 1000 arasında olmalı.")
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute("SET LOCAL transaction_read_only = on")
            imlec.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (str(zaman_asimi_ms),),
            )
            imlec.execute(ifade, prepare=True)
            sutunlar = [s.name for s in imlec.description or []]
            return [
                dict(zip(sutunlar, satir, strict=True))
                for satir in imlec.fetchmany(limit)
            ]
