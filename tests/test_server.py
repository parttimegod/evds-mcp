"""MCP araçlarının testleri.

Araçlar _baglan() ile gerçek istemciyi kuruyor; testlerde modül
seviyesindeki iki global'i sahtelerle değiştiriyoruz.
"""

import json
from datetime import date
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from evds_mcp import server
from evds_mcp.catalog import Katalog
from evds_mcp.client import Gozlem, Seri
from evds_mcp.server import _frekans_dogrula, _ozet, _tarih_oku

FIXTURES = Path(__file__).parent / "fixtures"


def ham_gruplar():
    return json.loads((FIXTURES / "datagroups_tumu.json").read_text(encoding="utf-8"))


def ham_seriler():
    return json.loads((FIXTURES / "serielist_bie_tufe1.json").read_text(encoding="utf-8"))


class SahteEVDS:
    def __init__(self, gozlem_sayisi=100):
        self.gozlem_sayisi = gozlem_sayisi
        self.son_cagri = None

    def veri(self, kodlar, baslangic, bitis, frekans="aylık"):
        self.son_cagri = (kodlar, baslangic, bitis, frekans)
        return [
            Seri(
                kod=k,
                gozlemler=[
                    Gozlem(tarih=f"2020-{i + 1}", deger=float(100 + i))
                    for i in range(self.gozlem_sayisi)
                ],
            )
            for k in kodlar
        ]

    def veri_gruplari(self):
        return ham_gruplar()

    def grup_serileri(self, grup_kodu):
        return ham_seriler() if grup_kodu.startswith("bie_") else []


@pytest.fixture
def sahte(monkeypatch):
    e = SahteEVDS()
    monkeypatch.setattr(server, "_evds", e)
    monkeypatch.setattr(server, "_katalog", Katalog(e))
    return e


def test_tarih_birkac_formati_okuyor():
    assert _tarih_oku("2020-01-15", "start") == date(2020, 1, 15)
    assert _tarih_oku("15-01-2020", "start") == date(2020, 1, 15)
    assert _tarih_oku("2020-01", "start") == date(2020, 1, 1)
    assert _tarih_oku("2020", "start") == date(2020, 1, 1)


def test_bozuk_tarih_ornekli_hata():
    with pytest.raises(ToolError, match="2020-01-01"):
        _tarih_oku("ocak 2020", "start")


def test_bilinmeyen_frekans_secenekleri_sayiyor():
    with pytest.raises(ToolError, match="aylık"):
        _frekans_dogrula("montly")


def test_ozet_hesapliyor():
    g = [Gozlem("2020-1", 100.0), Gozlem("2020-2", None), Gozlem("2020-3", 150.0)]
    o = _ozet(g)

    assert o["gozlem"] == 3
    assert o["eksik"] == 1
    assert o["ilk"] == 100.0
    assert o["son"] == 150.0
    assert o["max"] == 150.0
    assert o["toplam_degisim_yuzde"] == 50.0


def test_ozet_tamamen_bos_seri():
    o = _ozet([Gozlem("2020-1", None)])

    assert o["eksik"] == 1
    assert "not" in o


def test_get_series_varsayilan_kirpiyor(sahte):
    d = server.get_series(codes=["TP.X"], start="2020-01-01", end="2026-01-01")
    seri = d["seriler"][0]

    assert seri["ozet"]["gozlem"] == 100          # özet tamamını kapsıyor
    assert len(seri["veri"]) == server.PENCERE    # dönen veri dar
    assert d["kirpildi"] is True
    assert "full=True" in d["not"]


def test_get_series_full_hepsini_veriyor(sahte):
    d = server.get_series(
        codes=["TP.X"], start="2020-01-01", end="2026-01-01", full=True
    )

    assert len(d["seriler"][0]["veri"]) == 100
    assert "kirpildi" not in d


def test_kisa_seri_kirpilmiyor(monkeypatch):
    e = SahteEVDS(gozlem_sayisi=5)
    monkeypatch.setattr(server, "_evds", e)
    monkeypatch.setattr(server, "_katalog", Katalog(e))

    d = server.get_series(codes=["TP.X"], start="2020-01-01", end="2020-06-01")

    assert len(d["seriler"][0]["veri"]) == 5
    assert "kirpildi" not in d


def test_get_series_bos_kod_listesi_yol_gosteriyor(sahte):
    with pytest.raises(ToolError, match="search_series"):
        server.get_series(codes=[], start="2020-01-01", end="2020-06-01")


def test_summarize_ham_veri_dondurmuyor(sahte):
    d = server.summarize_series(code="TP.X", start="2020-01-01", end="2026-01-01")

    assert "ozet" in d
    assert "veri" not in d


def test_search_kunye_donduruyor(sahte):
    d = server.search_series(query="enflasyon", limit=5)

    assert d["seriler"]
    ilk = d["seriler"][0]
    assert {"kod", "ad", "frekans", "kapsam", "kaynak"} <= set(ilk)


def test_search_limiti_asmiyor(sahte):
    d = server.search_series(query="faiz", limit=4)
    assert len(d["seriler"]) <= 4


def test_search_sonucsuz_sorgu_oneri_veriyor(sahte):
    with pytest.raises(ToolError, match="dene"):
        server.search_series(query="zxqwerty", limit=5)


def test_frekans_istemciye_geciyor(sahte):
    server.get_series(
        codes=["TP.X"], start="2020-01-01", end="2020-06-01", frequency="yıllık"
    )
    assert sahte.son_cagri[3] == "yıllık"
