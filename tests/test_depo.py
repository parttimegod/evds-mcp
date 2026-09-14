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
from decimal import Decimal

import pytest

from evds_mcp.catalog import SeriKunye
from evds_mcp.client import Gozlem
from evds_mcp.depo import Depo, DepoHatasi

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


def _ornek_kunye(
    kod: str = "TP.TEST", ad: str = "Test Serisi", frekans: str = "AYLIK"
) -> SeriKunye:
    return SeriKunye(
        kod=kod,
        ad=ad,
        ad_eng="Test Series",
        grup_kodu="test_group",
        frekans=frekans,
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
    depo.gozlem_yaz(
        "TP.TEST", date(2020, 1, 1), date(2020, 1, 31), [Gozlem("2020-1", 1.0)]
    )
    depo.gozlem_yaz(
        "TP.TEST", date(2020, 1, 1), date(2020, 1, 31), [Gozlem("2020-1", 2.0)]
    )

    sonuc = depo.gozlem_oku("TP.TEST", date(2020, 1, 1), date(2020, 1, 31))

    assert len(sonuc) == 1
    assert sonuc[0].deger == 2.0


def test_null_gozlem_none_donuyor(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST", date(2020, 2, 1), date(2020, 2, 29), [Gozlem("2020-2", None)]
    )

    sonuc = depo.gozlem_oku("TP.TEST", date(2020, 2, 1), date(2020, 2, 28))

    assert len(sonuc) == 1
    assert sonuc[0].deger is None


def test_ham_donem_orijinal_metni_koruyor(depo):
    # EVDS'nin gönderdiği ham dönem etiketi tarih'e parse edilirken
    # kayboluyor olmasın diye ayrıca saklanıyor -- bkz. sema.sql.
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST", date(2020, 3, 1), date(2020, 3, 31), [Gozlem("2020-3", 3.0)]
    )

    sonuc = depo.gozlem_oku("TP.TEST", date(2020, 3, 1), date(2020, 3, 31))

    assert sonuc[0].ham_donem == "2020-3"
    assert sonuc[0].tarih == date(2020, 3, 1)


def test_son_gozlemler_yeniden_eskiye_siralanir_ve_sayiyi_sinirlar(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST",
        date(2020, 1, 1),
        date(2020, 6, 30),
        [Gozlem(f"2020-{ay}", float(ay)) for ay in range(1, 7)],
    )

    son = depo.son_gozlemler("TP.TEST", 3)

    assert [g.tarih.month for g in son] == [6, 5, 4]
    assert [g.deger for g in son] == [6.0, 5.0, 4.0]


def test_gecikmeli_oku_dogru_onceki_degeri_ve_ilk_satirlarda_none_verir(depo):
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST",
        date(2020, 1, 1),
        date(2020, 6, 30),
        [Gozlem(f"2020-{ay}", float(ay)) for ay in range(1, 7)],
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


def test_satir_tabanli_ve_takvim_tabanli_lag_bosluklu_seride_ayrisir(depo):
    """LAG trap'in ta kendisi: bu test bu değişikliğin tüm amacı.

    Mart'ı (2020-3) hiç yazmıyoruz -- NULL değerli bir satır değil,
    satırın kendisi yok. Nisan'ın satır-tabanlı LAG(1)'i bu durumda
    Şubat'ın değerini döner ve bunu yanlışlıkla "1 ay önce" diye
    etiketler (gerçekte 2 takvim ayı önce). Takvim tabanlı sürüm Mart'ı
    açık bir NULL satırı olarak izgaraya koyduğu için Nisan'ın 1 ay
    öncesinin bilinmediğini doğru şekilde None döner.
    """
    depo.seri_yaz(_ornek_kunye())
    depo.gozlem_yaz(
        "TP.TEST",
        date(2020, 1, 1),
        date(2020, 6, 30),
        [
            Gozlem("2020-1", 1.0),
            Gozlem("2020-2", 2.0),
            # 2020-3 kasıtlı olarak yok.
            Gozlem("2020-4", 4.0),
            Gozlem("2020-5", 5.0),
            Gozlem("2020-6", 6.0),
        ],
    )

    satir_tabanli = depo.gecikmeli_oku("TP.TEST", 1)
    takvim_tabanli = depo.takvim_gecikmeli_oku("TP.TEST", 1)

    nisan_satir = next(s for s in satir_tabanli if s.tarih == date(2020, 4, 1))
    nisan_takvim = next(s for s in takvim_tabanli if s.tarih == date(2020, 4, 1))

    # Satır tabanlı: Mart'ın yokluğunu fark etmiyor, Şubat'ı (2.0) "1 ay
    # önce" diye etiketliyor -- bu yanlış, gerçekte 2 ay önce.
    assert nisan_satir.deger == 4.0
    assert nisan_satir.onceki == 2.0

    # Takvim tabanlı: Mart izgarada NULL bir satır olarak var, bu yüzden
    # Nisan'ın 1 ay öncesi doğru şekilde bilinmiyor (None).
    assert nisan_takvim.deger == 4.0
    assert nisan_takvim.onceki is None

    # 5 gözlem (satır) var ama takvim tabanlı izgara Mart'ı da NULL
    # satır olarak eklediği için 6 satır dönüyor.
    assert len(satir_tabanli) == 5
    assert len(takvim_tabanli) == 6


def test_takvim_gecikmeli_oku_isgunu_ve_haftalik_icin_acik_hata_verir(depo):
    depo.seri_yaz(_ornek_kunye(kod="TP.ISGUNU", frekans="İŞ GÜNÜ"))
    depo.seri_yaz(_ornek_kunye(kod="TP.HAFTA", frekans="HAFTALIK(CUMA)"))

    with pytest.raises(DepoHatasi, match="işgünü"):
        depo.takvim_gecikmeli_oku("TP.ISGUNU", 1)
    with pytest.raises(DepoHatasi, match="haftalık"):
        depo.takvim_gecikmeli_oku("TP.HAFTA", 1)


def test_numeric_tam_yuvarlamasiz_gidip_geliyor(depo):
    depo.seri_yaz(_ornek_kunye())
    # float ile 0.1 + 0.2 == 0.30000000000000004 -- tam Decimal
    # toplamıyla bu yuvarlama hiç oluşmuyor.
    tam_deger = Decimal("0.1") + Decimal("0.2")
    assert tam_deger == Decimal("0.3")

    depo.gozlem_yaz(
        "TP.TEST", date(2020, 1, 1), date(2020, 1, 31), [Gozlem("2020-1", tam_deger)]
    )

    sonuc = depo.gozlem_oku("TP.TEST", date(2020, 1, 1), date(2020, 1, 31))

    assert isinstance(sonuc[0].deger, Decimal)
    assert sonuc[0].deger == Decimal("0.3")


def test_cekim_denetim_satiri_dogru_sayilari_tutuyor(depo):
    depo.seri_yaz(_ornek_kunye())
    yazilan = depo.gozlem_yaz(
        "TP.TEST",
        date(2020, 1, 1),
        date(2020, 3, 31),
        [Gozlem("2020-1", 1.0), Gozlem("2020-2", None), Gozlem("2020-3", 3.0)],
    )
    assert yazilan == 3

    kayitlar = depo.cekimler_oku("TP.TEST")

    assert len(kayitlar) == 1
    kayit = kayitlar[0]
    assert kayit.istenen_baslangic == date(2020, 1, 1)
    assert kayit.istenen_bitis == date(2020, 3, 31)
    assert kayit.gozlem_sayisi == 3
    assert kayit.null_sayisi == 1


def test_cekim_ters_aralikta_hata_verir(depo):
    depo.seri_yaz(_ornek_kunye())
    with pytest.raises(DepoHatasi, match="bitişten sonra"):
        depo.gozlem_yaz(
            "TP.TEST", date(2020, 3, 1), date(2020, 1, 1), [Gozlem("2020-1", 1.0)]
        )


def test_salt_okunur_sorgu_select_calistirir_ve_satir_doner(depo):
    depo.seri_yaz(_ornek_kunye())

    sonuc = depo.salt_okunur_sorgu("SELECT kod, ad FROM seri")

    assert sonuc == [{"kod": "TP.TEST", "ad": "Test Serisi"}]


def test_salt_okunur_sorgu_yazma_ifadesini_reddeder(depo):
    with pytest.raises(DepoHatasi, match="SELECT, WITH, SHOW"):
        depo.salt_okunur_sorgu("DELETE FROM seri")


def test_salt_okunur_sorgu_cift_ifadeyi_reddeder(depo):
    with pytest.raises(DepoHatasi, match="tek bir SQL"):
        depo.salt_okunur_sorgu("SELECT 1; DELETE FROM seri")


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
