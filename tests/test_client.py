"""İstemcinin ağa çıkmayan kısımlarının testleri.

fixtures/aylik_iki_seri.json elle yazıldı -- dokümandaki şekle göre.
Anahtarı alınca gerçek bir yanıtla değiştir, şekil tutmuyorsa buradan
anlarız.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from evds_mcp.client import EVDS, EVDSHatasi, _sayiya_cevir, _sutun_bul, _tarih_yaz

FIXTURE = Path(__file__).parent / "fixtures" / "aylik_iki_seri.json"


def govde():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_tarih_gun_ay_yil_yaziliyor():
    # ISO yazarsak EVDS sessizce başka aralık döndürür.
    assert _tarih_yaz(date(2020, 3, 1)) == "01-03-2020"
    assert _tarih_yaz(date(2026, 12, 31)) == "31-12-2026"


def test_nokta_yerine_alt_cizgi_gelirse_bulunuyor():
    satir = {"Tarih": "2020-1", "TP_FG_J0": "12,5"}
    assert _sutun_bul(satir, "TP.FG.J0") == "TP_FG_J0"


def test_noktali_hali_de_bulunuyor():
    satir = {"Tarih": "2020-1", "TP.FG.J0": "1"}
    assert _sutun_bul(satir, "TP.FG.J0") == "TP.FG.J0"


def test_olmayan_sutun_none():
    assert _sutun_bul({"Tarih": "2020-1"}, "TP.FG.J0") is None


@pytest.mark.parametrize(
    "ham, beklenen",
    [
        ("12.5", 12.5),
        ("0", 0.0),
        ("", None),
        (None, None),
        ("yok", None),
    ],
)
def test_sayiya_cevirme(ham, beklenen):
    assert _sayiya_cevir(ham) == beklenen


def test_iki_seri_ayikliyor():
    seriler = EVDS._ayikla(govde(), ["TP.FG.J0", "TP.APIFON4"])

    assert [s.kod for s in seriler] == ["TP.FG.J0", "TP.APIFON4"]
    assert len(seriler[0].gozlemler) == 3
    assert seriler[0].gozlemler[0].tarih == "2020-1"
    assert seriler[0].gozlemler[0].deger == 452.51


def test_eksik_gozlem_none_oluyor():
    seriler = EVDS._ayikla(govde(), ["TP.APIFON4"])
    degerler = [g.deger for g in seriler[0].gozlemler]

    assert degerler == [11.43, None, 10.75]
    assert seriler[0].dolu_sayisi == 2


def test_olmayan_seri_bos_donuyor_digerleri_geliyor():
    # Bir kod yanlışsa tüm çağrıyı patlatmak yerine o seriyi boş bırak.
    seriler = EVDS._ayikla(govde(), ["TP.FG.J0", "TP.OLMAYAN"])

    assert seriler[0].gozlemler != []
    assert seriler[1].gozlemler == []


def test_bos_items_anlamli_hata():
    with pytest.raises(EVDSHatasi, match="gözlem yok"):
        EVDS._ayikla({"items": []}, ["TP.FG.J0"])
