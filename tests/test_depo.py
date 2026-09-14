"""Depo testleri. Gerçek PostgreSQL gerektiriyor, varsayılan olarak atlanır:

    uv run pytest -m depo

Kendi şeması (`depo_test`) içinde çalışır ve her testten önce/sonra o
şemayı silip yeniden kurar -- gerçek veriye dokunmaz. Bağlantı bilgisi
EVDS_TEST_DATABASE_URL ile değiştirilebilir, yoksa canlı test veritabanı
kurulumundaki varsayılan trust-auth bağlantısı kullanılır.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from evds_mcp.catalog import SeriKunye
from evds_mcp.client import Gozlem
from evds_mcp.depo import Depo

pytestmark = pytest.mark.depo

_ANA_DSN = os.environ.get(
    "EVDS_TEST_DATABASE_URL", "host=127.0.0.1 port=5432 dbname=evds user=postgres"
)
_SEMA_ADI = "depo_test"
# libpq'nun "options" parametresi arka uca komut satırı argümanı geçiyor;
# search_path'i burada ayarlamak Depo'nun sabit `seri`/`gozlem` adlarına
# hiç dokunmadan testleri kendi şemasına hapsediyor.
_TEST_DSN = f"{_ANA_DSN} options='-c search_path={_SEMA_ADI}'"


def _ham_baglanti():
    # psycopg burada da gecikmeli: modül üst seviyede import edilirse
    # kurulu değilken bu dosyanın toplanması (collection) bile patlar,
    # oysa marker sayesinde testler zaten çalıştırılmıyor olmalı.
    pytest.importorskip("psycopg")
    import psycopg

    return psycopg.connect(_ANA_DSN, autocommit=True)


@pytest.fixture
def depo():
    with _ham_baglanti() as baglanti, baglanti.cursor() as imlec:
        imlec.execute(f"DROP SCHEMA IF EXISTS {_SEMA_ADI} CASCADE")
        imlec.execute(f"CREATE SCHEMA {_SEMA_ADI}")
    d = Depo(_TEST_DSN)
    d.kur()
    try:
        yield d
    finally:
        with _ham_baglanti() as baglanti, baglanti.cursor() as imlec:
            imlec.execute(f"DROP SCHEMA IF EXISTS {_SEMA_ADI} CASCADE")


def _ornek_kunye(kod: str = "TP.TEST", ad: str = "Test Serisi") -> SeriKunye:
    return SeriKunye(
        kod=kod,
        ad=ad,
        ad_eng="Test Series",
        grup_kodu="test_group",
        frekans="AYLIK",
        kaynak="TEST",
        toplama="son",
        baslangic="01-01-2020",
        bitis="01-12-2020",
        sira=1,
    )


def test_sema_iki_kez_uygulanir(depo):
    # kur() ikinci kez çağrılınca patlamamalı -- CREATE ... IF NOT EXISTS.
    depo.kur()


def test_ayni_gozlem_tekrar_yazilinca_cift_olmuyor_ikincisi_kazaniyor(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz("TP.TEST", [Gozlem("2020-1", 1.0)])
    depo.gozlem_yaz("TP.TEST", [Gozlem("2020-1", 2.0)])

    sonuc = depo.gozlem_oku("TP.TEST", date(2020, 1, 1), date(2020, 1, 31))

    assert len(sonuc) == 1
    assert sonuc[0].deger == 2.0


def test_null_gozlem_none_donuyor(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz("TP.TEST", [Gozlem("2020-2", None)])

    sonuc = depo.gozlem_oku("TP.TEST", date(2020, 2, 1), date(2020, 2, 28))

    assert len(sonuc) == 1
    assert sonuc[0].deger is None


def test_son_gozlemler_yeniden_eskiye_siralanir_ve_sayiyi_sinirlar(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST", [Gozlem(f"2020-{ay}", float(ay)) for ay in range(1, 7)]
    )

    son = depo.son_gozlemler("TP.TEST", 3)

    assert [g.tarih.month for g in son] == [6, 5, 4]
    assert [g.deger for g in son] == [6.0, 5.0, 4.0]


def test_gecikmeli_oku_dogru_onceki_degeri_ve_ilk_satirlarda_none_verir(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST", [Gozlem(f"2020-{ay}", float(ay)) for ay in range(1, 7)]
    )

    sonuc = depo.gecikmeli_oku("TP.TEST", 2)

    assert len(sonuc) == 6
    # İlk 2 satırda (Ocak, Şubat) 2 dönem öncesi yok -> None.
    assert [s.onceki for s in sonuc[:2]] == [None, None]
    # Mart (3.0), 2 gecikmeyle Ocak'ın (1.0) değerini görmeli.
    assert sonuc[2].deger == 3.0
    assert sonuc[2].onceki == 1.0
    # Haziran (6.0), 2 gecikmeyle Nisan'ın (4.0) değerini görmeli.
    assert sonuc[-1].deger == 6.0
    assert sonuc[-1].onceki == 4.0


def test_turkce_ad_bozulmadan_donuyor(depo):
    turkce_ad = "Tüketici Fiyat Endeksi (Genel) İşgücü Ölçümü Çığır Şıppadak"
    depo.seri_yaz(_ornek_kunye(ad=turkce_ad))

    with _ham_baglanti() as baglanti, baglanti.cursor() as imlec:
        imlec.execute(f"SET search_path TO {_SEMA_ADI}")
        imlec.execute("SELECT ad FROM seri WHERE kod = %s", ("TP.TEST",))
        (donen,) = imlec.fetchone()

    # Bilerek len() ile karşılaştırıyoruz, konsol çıktısıyla değil --
    # konsol Türkçe karakterleri güvenilmez şekilde gösterebiliyor.
    assert len(donen) == len(turkce_ad)
