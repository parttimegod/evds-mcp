"""İstemcinin ağa çıkmayan kısımları.

fixtures/ altındakiler gerçek EVDS yanıtları, bir kez kaydedildi.
Servis şekil değiştirirse önce buradaki testler kırılır -- amaç bu.

Canlı API'ye vuran tek test aşağıda, varsayılan olarak atlanıyor:
    uv run pytest -m live
"""

import json
import os
from datetime import date
from pathlib import Path

import pytest

from evds_mcp.client import (
    EVDS,
    EVDSHatasi,
    _parametre_yaz,
    _sayiya_cevir,
    _sutun_bul,
    _tarih_yaz,
)

FIXTURES = Path(__file__).parent / "fixtures"


def veri_govdesi():
    return json.loads((FIXTURES / "veri_aylik_iki_seri.json").read_text(encoding="utf-8"))


def test_tarih_gun_ay_yil_yaziliyor():
    # ISO yazarsak EVDS hata vermeden başka aralık döndürür.
    assert _tarih_yaz(date(2020, 3, 1)) == "01-03-2020"
    assert _tarih_yaz(date(2026, 12, 31)) == "31-12-2026"


def test_parametreler_soru_isaretsiz_zincirleniyor():
    assert _parametre_yaz(type="json", code="bie_tufe1") == "type=json&code=bie_tufe1"


def test_bos_string_parametre_korunuyor():
    # datagroups ucu "code=" görmek istiyor.
    assert _parametre_yaz(mode=0, code="", type="json") == "mode=0&code=&type=json"


def test_none_parametre_atiliyor():
    assert _parametre_yaz(type="json", frequency=None) == "type=json"


def test_nokta_yerine_alt_cizgi_gelirse_bulunuyor():
    satir = {"Tarih": "2020-1", "TP_FG_J0": "446.45000000"}
    assert _sutun_bul(satir, "TP.FG.J0") == "TP_FG_J0"


def test_noktali_hali_de_bulunuyor():
    assert _sutun_bul({"TP.FG.J0": "1"}, "TP.FG.J0") == "TP.FG.J0"


def test_olmayan_sutun_none():
    assert _sutun_bul({"Tarih": "2020-1"}, "TP.FG.J0") is None


@pytest.mark.parametrize(
    "ham, beklenen",
    [
        ("446.45000000", 446.45),
        ("0", 0.0),
        ("", None),
        (None, None),
        ("yok", None),
    ],
)
def test_sayiya_cevirme(ham, beklenen):
    assert _sayiya_cevir(ham) == beklenen


def test_iki_seri_ayikliyor():
    seriler = EVDS._ayikla(veri_govdesi(), ["TP.FG.J0", "TP.APIFON4"])

    assert [s.kod for s in seriler] == ["TP.FG.J0", "TP.APIFON4"]
    assert len(seriler[0].gozlemler) == 6
    assert seriler[0].gozlemler[0].tarih == "2020-1"
    assert seriler[0].gozlemler[0].deger == 446.45
    assert seriler[1].gozlemler[0].deger == 10.97


def test_eksik_gozlem_none_oluyor():
    govde = {
        "items": [
            {"Tarih": "2020-1", "TP_APIFON4": "10.97000000"},
            {"Tarih": "2020-2", "TP_APIFON4": ""},
            {"Tarih": "2020-3", "TP_APIFON4": "9.27000000"},
        ]
    }
    (seri,) = EVDS._ayikla(govde, ["TP.APIFON4"])

    assert [g.deger for g in seri.gozlemler] == [10.97, None, 9.27]
    assert seri.dolu_sayisi == 2


def test_olmayan_seri_bos_donuyor_digerleri_geliyor():
    # Bir kod yanlışsa tüm çağrıyı patlatmak yerine o seriyi boş bırak.
    seriler = EVDS._ayikla(veri_govdesi(), ["TP.FG.J0", "TP.OLMAYAN"])

    assert seriler[0].gozlemler != []
    assert seriler[1].gozlemler == []


def test_bos_items_anlamli_hata():
    with pytest.raises(EVDSHatasi, match="gözlem yok"):
        EVDS._ayikla({"items": []}, ["TP.FG.J0"])


def test_serielist_fixture_turkce_bozulmamis():
    seriler = json.loads((FIXTURES / "serielist_bie_tufe1.json").read_text(encoding="utf-8"))
    adlar = " ".join(s["SERIE_NAME"] for s in seriler)

    assert "�" not in adlar  # bozuk karakter yok
    assert "ş" in adlar or "İ" in adlar or "ı" in adlar


@pytest.mark.live
def test_canli_veri_cekiyor():
    if not os.environ.get("EVDS_API_KEY"):
        pytest.skip("EVDS_API_KEY yok")

    with EVDS() as evds:
        (seri,) = evds.veri(["TP.FG.J0"], date(2020, 1, 1), date(2020, 6, 1))

    assert len(seri.gozlemler) == 6
    assert seri.gozlemler[0].deger == 446.45
