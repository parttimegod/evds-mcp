"""Katalog ve arama testleri.

datagroups_tumu.json gerçek EVDS yanıtı, 676 grubun tamamı. Sadece
kullandığımız altı alana kırpıldı, yoksa 1 MB'ı geçiyordu.

Aşağıdaki "bulunuyor" testleri asıl değerli olanlar: arama bozulursa
önce onlar kırılır.
"""

import json
from pathlib import Path

import pytest

from evds_mcp.catalog import (
    Katalog,
    _arsiv_mi,
    _genislet,
    _grup_yap,
    _puan,
    _seri_yap,
    _sirala,
)
from evds_mcp.client import EVDSHatasi

FIXTURES = Path(__file__).parent / "fixtures"


def ham_gruplar():
    return json.loads((FIXTURES / "datagroups_tumu.json").read_text(encoding="utf-8"))


def ham_seriler():
    return json.loads((FIXTURES / "serielist_bie_tufe1.json").read_text(encoding="utf-8"))


@pytest.fixture
def gruplar():
    return [_grup_yap(h) for h in ham_gruplar()]


class SahteEVDS:
    """Ağa çıkmayan istemci. Kaç kez çağrıldığını da sayıyor."""

    def __init__(self):
        self.grup_cagrisi = 0

    def veri_gruplari(self):
        self.grup_cagrisi += 1
        return ham_gruplar()

    def grup_serileri(self, grup_kodu):
        return ham_seriler() if grup_kodu == "bie_tufe1" else []


def test_puan_tam_kelime_daha_degerli():
    assert _puan("faiz", "politika faiz orani") == 2
    assert _puan("faiz", "faizsiz bankacilik") == 1
    assert _puan("faiz", "konut fiyat endeksi") == 0


def test_puan_kismi_eslesme_de_sayiliyor():
    # "cari acik" -> "acik" adda geçmiyor ama "cari" geçiyor.
    assert _puan("cari acik", "cari islemler dengesi") == 2


def test_esanlamli_genisletme():
    assert "isgucu" in _genislet("issizlik")
    assert "hasila" in _genislet("buyume")


def test_esanlamlisi_olmayan_sorgu_degismiyor():
    assert _genislet("konut fiyat") == "konut fiyat"


def test_arsiv_tespiti():
    assert _arsiv_mi("Konut Fiyat Endeksi (Arşiv)")
    assert not _arsiv_mi("Konut Fiyat Endeksi")


@pytest.mark.parametrize(
    "sorgu, beklenen_kod",
    [
        ("konut fiyat", "bie_kfe"),
        ("politika faizi", "bie_bispolfaiz"),
        ("issizlik", "bie_yisgucu2"),
        ("isgucu", "bie_yisgucu2"),
    ],
)
def test_bilinen_sorgular_dogru_grubu_buluyor(gruplar, sorgu, beklenen_kod):
    kodlar = [g.kod for g in _sirala(gruplar, sorgu, 5)]
    assert beklenen_kod in kodlar


@pytest.mark.parametrize("sorgu", ["enflasyon", "buyume", "cari acik", "doviz kuru"])
def test_yaygin_sorgular_bos_donmuyor(gruplar, sorgu):
    # Bunlar eşanlamlı sözlüğü olmadan sıfır sonuç veriyordu.
    assert _sirala(gruplar, sorgu, 5)


def test_enflasyon_tufeye_gidiyor(gruplar):
    adlar = " ".join(g.ad for g in _sirala(gruplar, "enflasyon", 5))
    assert "Tüketici Fiyat" in adlar


def test_arsiv_gerilere_dusuyor(gruplar):
    sonuc = _sirala(gruplar, "konut fiyat", 10)
    ilk_arsivsiz = next(i for i, g in enumerate(sonuc) if not _arsiv_mi(g.ad))
    ilk_arsivli = next((i for i, g in enumerate(sonuc) if _arsiv_mi(g.ad)), None)

    assert ilk_arsivli is None or ilk_arsivsiz < ilk_arsivli


def test_bos_sorgu_hata(gruplar):
    with pytest.raises(EVDSHatasi, match="boş"):
        _sirala(gruplar, "   ", 5)


def test_limit_uyuluyor(gruplar):
    assert len(_sirala(gruplar, "faiz", 3)) == 3


def test_gruplar_bir_kez_cekiliyor():
    sahte = SahteEVDS()
    k = Katalog(sahte)

    k.grup_ara("faiz")
    k.grup_ara("konut")
    k.gruplar()

    assert sahte.grup_cagrisi == 1


def test_seri_kunyesi_ayikliyor():
    kunye = _seri_yap(ham_seriler()[0])

    assert kunye.kod.startswith("TP.")
    assert kunye.grup_kodu == "bie_tufe1"
    assert kunye.frekans == "AYLIK"
    assert kunye.toplama  # "last" gibi


def test_grup_icinde_seri_aramasi():
    k = Katalog(SahteEVDS())
    sonuc = k.seri_ara("genel", "bie_tufe1")

    assert sonuc
    assert all(s.grup_kodu == "bie_tufe1" for s in sonuc)


def test_bos_grup_yol_gosteren_hata():
    k = Katalog(SahteEVDS())
    with pytest.raises(EVDSHatasi, match="grup_ara"):
        k.grup_serileri("bie_olmayan")


def test_kunye_kapsam_tarihlerini_tasiyor():
    # Arşivlenmiş seri veriyi çekmeden buradan anlaşılsın.
    kunye = _seri_yap(ham_seriler()[0])

    assert kunye.baslangic == "01-01-2003"
    assert kunye.bitis == "01-12-2013"


def test_seri_aramasi_elemiyor_siraliyor():
    # Grup adı eşleşse de seri adları sorgu kelimesini içermiyor olabilir.
    # Bu durumda boş dönmek yerine EVDS'nin ekran sırasına düşmeli.
    k = Katalog(SahteEVDS())
    sonuc = k.seri_ara("enflasyon", "bie_tufe1", limit=5)

    assert sonuc, "grup eşleştiyse seri listesi boş dönmemeli"


def test_turkiye_tespiti():
    from evds_mcp.catalog import _turkiye_mi

    tr = _seri_yap({"SERIE_CODE": "TP.BISPOLFAIZ.TUR", "SERIE_NAME": "Türkiye (TUR)"})
    de = _seri_yap({"SERIE_CODE": "TP.BISPOLFAIZ.DEU", "SERIE_NAME": "Almanya (DEU)"})

    assert _turkiye_mi(tr)
    assert not _turkiye_mi(de)


def test_ekran_sirasi_okunuyor():
    kunye = _seri_yap({"SERIE_CODE": "TP.X", "SCREEN_ORDER": 470})
    assert kunye.sira == 470


def test_ekran_sirasi_yoksa_sona():
    assert _seri_yap({"SERIE_CODE": "TP.X"}).sira == 9999


@pytest.mark.parametrize("sorgu", ["dolar kuru", "amerikan doları alış", "euro kuru"])
def test_nominal_kur_grubunu_buluyor(gruplar, sorgu):
    # Nominal kur grubunun adı sadece "Döviz Kurları"; "dolar" içinde
    # geçmiyor. Eşanlamlı olmadan bu sorgular reel efektif kura düşüyordu.
    assert _sirala(gruplar, sorgu, 3)[0].kod == "bie_dkdovytl"


def test_turkce_ekler_onek_eslesmesiyle_yakalaniyor():
    # "doları" tam eşleşmiyor ama "dolar" ile başlıyor.
    assert "doviz kurlari" in _genislet("dolari")
    assert "doviz kurlari" in _genislet("dolarin")


def test_kisa_kokler_onek_eslesmesine_girmiyor():
    # "kur" kökü "kurumsal", "kuruluş" gibi kelimeleri yakalamamalı.
    assert "doviz kurlari" not in _genislet("kurumsal")


@pytest.mark.parametrize(
    "sorgu, beklenen",
    [
        ("dollar exchange rate", "bie_dkdovytl"),
        ("unemployment", "bie_yisgucu2"),
        ("policy rate", "bie_bispolfaiz"),
    ],
)
def test_ingilizce_sorgular(gruplar, sorgu, beklenen):
    # Grup adlarının İngilizcesi de aranıyor ama kullanıcının kelimesi
    # tutmayabiliyor: "dollar" arayan "Exchange Rates"i bulamıyordu.
    assert beklenen in [g.kod for g in _sirala(gruplar, sorgu, 3)]


def test_grup_icinde_esanlamli_kullanilmiyor():
    """Sözlük grup bulmak için; grup içinde sorguyu bozuyor.

    "işsizlik oranı" -> "istihdam" ile genişleyince gruptaki
    "İstihdam oranı" öne çıkıp "İşsizlik oranı"nı geriye atıyordu.
    """
    seriler = [
        _seri_yap({"SERIE_CODE": "G6", "SERIE_NAME": "6.İşgücüne katılma oranı (%)"}),
        _seri_yap({"SERIE_CODE": "G7", "SERIE_NAME": "7.İstihdam oranı (%)"}),
        _seri_yap({"SERIE_CODE": "G8", "SERIE_NAME": "8.İşsizlik oranı (%)"}),
    ]

    class TekGrup(SahteEVDS):
        def grup_serileri(self, grup_kodu):
            return [
                {"SERIE_CODE": s.kod, "SERIE_NAME": s.ad, "DATAGROUP_CODE": "bie_x"}
                for s in seriler
            ]

    sonuc = Katalog(TekGrup()).seri_ara("işsizlik oranı", "bie_x", limit=3)
    assert sonuc[0].kod == "G8"
