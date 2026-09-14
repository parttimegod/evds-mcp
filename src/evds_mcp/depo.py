"""EVDS verisi için opsiyonel PostgreSQL depolama katmanı.

İki amacı var: aynı seriyi tekrar tekrar EVDS'den çekmemek (istek sayısı
sınırlı ve yavaş), ve geçmiş veriyi SQL ile sorgulayabilmek -- client.py
tek seferlik istek/yanıt veriyor, geçmişe dönük analiz için bir yer yok.

Bu katman tamamen opsiyonel: psycopg pyproject.toml'da `depo` ekstrası
altında, ana paket PostgreSQL kurulu olmadan da çalışmaya devam ediyor.
Bu yüzden psycopg modül yüklenirken değil, ilk gerçek kullanımda
içeri alınıyor -- `import evds_mcp` psycopg'siz bir makinede patlamamalı.

Şema iki tablo: seri (künye) ve gozlem (değerler), sema.sql'de. Tasarım
kararları orada satır satır yorumlanmış durumda.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
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
    deger: float | None


@dataclass(frozen=True)
class GecikmeliGozlem:
    tarih: date
    deger: float | None
    onceki: float | None  # `gecikme` dönem önceki değer; yoksa None


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
    sessizce yanlış bir tarih saklamak yerine hata veriyoruz.
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

    def gozlem_yaz(self, kod: str, gozlemler: list[Gozlem]) -> int:
        """Gözlemleri toplu upsert eder; yazılan satır sayısını döner.

        executemany kullanıyoruz, COPY değil. COPY sadece ekleme yapıyor;
        burada gereken idempotent upsert (ON CONFLICT DO UPDATE) COPY ile
        doğrudan olmuyor, bir staging tabloya kopyalayıp sonra ayrı bir
        merge adımı gerektirirdi. Tek bir EVDS isteği tipik olarak onlarca
        ile birkaç bin gözlem döndürüyor (bkz. client.py) -- bu ölçekte
        executemany'nin ek karmaşıklık gerektirmemesi, COPY'nin hız
        kazancından daha değerli.
        """
        satirlar = [(kod, _gozlem_tarihi(g.tarih), g.deger) for g in gozlemler]
        if not satirlar:
            return 0
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.executemany(
                """
                INSERT INTO gozlem (kod, tarih, deger, cekilme)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (kod, tarih) DO UPDATE SET
                    deger = EXCLUDED.deger,
                    cekilme = now()
                """,
                satirlar,
            )
        return len(satirlar)

    def gozlem_oku(self, kod: str, baslangic: date, bitis: date) -> list[DepoGozlem]:
        """[baslangic, bitis] aralığındaki gözlemleri tarihe göre artan döner."""
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                SELECT tarih, deger FROM gozlem
                WHERE kod = %s AND tarih BETWEEN %s AND %s
                ORDER BY tarih
                """,
                (kod, baslangic, bitis),
            )
            return [DepoGozlem(tarih=t, deger=d) for t, d in imlec.fetchall()]

    def son_gozlemler(self, kod: str, adet: int) -> list[DepoGozlem]:
        """Son `adet` gözlemi en yeniden en eskiye döner.

        gozlem_kod_tarih_desc_idx bu ORDER BY + LIMIT'i sort'suz bir
        indeks taramasına çeviriyor.
        """
        with self._baglan() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(
                """
                SELECT tarih, deger FROM gozlem
                WHERE kod = %s
                ORDER BY tarih DESC
                LIMIT %s
                """,
                (kod, adet),
            )
            return [DepoGozlem(tarih=t, deger=d) for t, d in imlec.fetchall()]

    def gecikmeli_oku(self, kod: str, gecikme: int) -> list[GecikmeliGozlem]:
        """Her gözlemi `gecikme` dönem önceki değeriyle birlikte döner.

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
