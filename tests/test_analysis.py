"""Metodoloji katmanının testleri.

Buradaki testler hesabın doğruluğundan çok, yanlış hesabın
engellendiğini gösteriyor. Seriler sentetik: gerçek veriyle test
edersek TCMB bir revizyon yaptığında testler kırılır.
"""

import math
import random

import pytest

from evds_mcp.analysis import (
    AnalizHatasi,
    donustur,
    duraganlik,
    fark,
    iliski,
    korelasyon,
    log_fark,
)


def beyaz_gurultu(n=200, tohum=0):
    r = random.Random(tohum)
    return [r.gauss(0, 1) for _ in range(n)]


def rassal_yuruyus(n=200, tohum=0, baslangic=100.0):
    r = random.Random(tohum)
    x, v = [], baslangic
    for _ in range(n):
        v += r.gauss(0, 1)
        x.append(v)
    return x


def iki_kez_butunlesik(n=200, tohum=0, baslangic=100.0):
    # Farkı rassal yürüyüş olan seri -> I(2)
    artis = rassal_yuruyus(n, tohum, baslangic=1.0)
    x, v = [], baslangic
    for a in artis:
        v += a
        x.append(v)
    return x


def test_fark_alma():
    assert fark([1.0, 3.0, 6.0]) == [2.0, 3.0]
    assert fark([1.0, 3.0, 6.0], 2) == [1.0]


def test_log_fark():
    x = [100.0, 110.0]
    assert log_fark(x)[0] == pytest.approx(math.log(1.1))


def test_log_fark_negatif_deger_reddediyor():
    with pytest.raises(AnalizHatasi, match="pozitif"):
        log_fark([1.0, -1.0])


def test_donustur_bilinmeyen():
    with pytest.raises(AnalizHatasi, match="Bilinmeyen"):
        donustur([1.0, 2.0], "karekok")


def test_duragan_seri_sifirinci_derece():
    d = duraganlik(beyaz_gurultu())

    assert d.derece == 0
    assert d.donusum == "seviye"


def test_rassal_yuruyus_birinci_derece():
    d = duraganlik(rassal_yuruyus())

    assert d.derece == 1
    assert d.p_degerleri["seviye"] > 0.05


def test_i2_seri_iki_fark_istiyor():
    d = duraganlik(iki_kez_butunlesik())

    assert d.derece == 2
    assert d.donusum == "d2"
    assert any("I(2)" in n for n in d.notlar)


def test_kisa_seri_anlamli_hata():
    with pytest.raises(AnalizHatasi, match="en az"):
        duraganlik([1.0, 2.0, 3.0])


def test_korelasyon_kendisiyle_bir():
    x = beyaz_gurultu()
    assert korelasyon(x, x) == pytest.approx(1.0)


def test_sabit_seri_korelasyonu_tanimsiz():
    with pytest.raises(AnalizHatasi, match="sabit"):
        korelasyon([1.0] * 30, beyaz_gurultu(30))


def test_iliski_ham_korelasyonu_uyariyla_veriyor():
    a = rassal_yuruyus(tohum=1)
    b = rassal_yuruyus(tohum=2)
    s = iliski(a, b, "A", "B")

    assert "ham_seviye_korelasyonu" in s
    assert "kullanma" in s["ham_seviye_korelasyonu"]["uyari"].lower()


def test_iliski_donusumu_bildiriyor():
    s = iliski(rassal_yuruyus(tohum=1), rassal_yuruyus(tohum=2), "A", "B")

    assert s["donusum"] in {"d1", "logd1"}
    assert s["duraganlik"]["A"]["derece"] == 1


def test_iliski_nedensellik_uyarisi_hep_var():
    s = iliski(rassal_yuruyus(tohum=3), rassal_yuruyus(tohum=4), "A", "B")

    assert "nedensellik" in s["yorum"].lower()


def test_farkli_dereceler_uyari_uretiyor():
    a = iki_kez_butunlesik(tohum=5)      # I(2)
    b = rassal_yuruyus(tohum=6)          # I(1)
    s = iliski(a, b, "A", "B")

    assert s["donusum"] == "d2"
    assert any("dereceleri farklı" in u for u in s["uyarilar"])


def test_uyarilar_seriye_atifli():
    s = iliski(iki_kez_butunlesik(tohum=7), rassal_yuruyus(tohum=8), "TUFE", "FAIZ")
    notlu = [u for u in s["uyarilar"] if u.startswith(("TUFE:", "FAIZ:"))]

    assert notlu, "notlar hangi seriye ait olduğu belirtilerek dönmeli"


def test_iki_i1_serisinde_esbutunlesme_test_ediliyor():
    s = iliski(rassal_yuruyus(tohum=9), rassal_yuruyus(tohum=10), "A", "B")

    assert "esbutunlesme" in s
    assert s["esbutunlesme"]["sonuc"] in {"var", "yok"}


def test_sahte_korelasyon_dusuyor():
    """Projenin varlık sebebi.

    İki bağımsız rassal yürüyüş seviyede yüksek korelasyon gösterebilir;
    durağanlaştırıldıktan sonra göstermemeli.
    """
    a = rassal_yuruyus(n=300, tohum=11)
    b = rassal_yuruyus(n=300, tohum=12)
    s = iliski(a, b, "A", "B")

    ham = abs(s["ham_seviye_korelasyonu"]["deger"])
    temiz = abs(s["korelasyon"])

    assert temiz < 0.2, "bağımsız serilerde dönüşüm sonrası korelasyon düşük olmalı"
    assert temiz < ham


def gecikmeli_seri(n=200, gecikme=2, tohum=0):
    """b, a'nın `gecikme` dönem sonraki yankısı olsun."""
    import random
    r = random.Random(tohum)
    a = [r.gauss(0, 1) for _ in range(n)]
    b = [0.0] * gecikme + [a[i - gecikme] + r.gauss(0, 0.3) for i in range(gecikme, n)]
    return a, b


def test_gecikme_tepesini_buluyor():
    from evds_mcp.analysis import gecikmeli_korelasyon

    a, b = gecikmeli_seri(gecikme=3)
    g = gecikmeli_korelasyon(a, b, maks_gecikme=8)

    assert g["tepe_gecikme"] == 3
    assert g["tepe_korelasyon"] > g["profil"][0]


def test_gecikme_profili_tam():
    from evds_mcp.analysis import gecikmeli_korelasyon

    a, b = gecikmeli_seri()
    g = gecikmeli_korelasyon(a, b, maks_gecikme=5)

    assert list(g["profil"]) == list(range(6))


def test_negatif_gecikme_reddediliyor():
    from evds_mcp.analysis import gecikmeli_korelasyon

    with pytest.raises(AnalizHatasi, match="negatif"):
        gecikmeli_korelasyon(beyaz_gurultu(), beyaz_gurultu(), maks_gecikme=-1)


def test_cok_buyuk_gecikme_reddediliyor():
    from evds_mcp.analysis import gecikmeli_korelasyon

    with pytest.raises(AnalizHatasi, match="yeterli gözlem"):
        gecikmeli_korelasyon(beyaz_gurultu(30), beyaz_gurultu(30), maks_gecikme=25)


def test_iliski_gecikmeyi_raporluyor():
    a, b = gecikmeli_seri(gecikme=2, tohum=3)
    s = iliski(a, b, "A", "B", maks_gecikme=6)

    assert s["gecikme"]["tepe_gecikme"] == 2
    assert any("gecikmede" in u for u in s["uyarilar"])


def test_zorlanan_donusum_uygulaniyor():
    a = rassal_yuruyus(tohum=20, baslangic=1000.0)
    b = rassal_yuruyus(tohum=21, baslangic=1000.0)
    s = iliski(a, b, "A", "B", donusum_zorla="logd1")

    assert s["donusum"] == "logd1"


def test_zorlanan_donusum_duraganlastirmiyorsa_uyariyor():
    a = iki_kez_butunlesik(tohum=22, baslangic=1000.0)
    b = rassal_yuruyus(tohum=23, baslangic=1000.0)
    s = iliski(a, b, "A", "B", donusum_zorla="logd1")

    assert any("durağanlaştırmıyor" in u for u in s["uyarilar"])
