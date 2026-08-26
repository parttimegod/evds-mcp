from evds_mcp.text import arama_anahtari, kucult


def test_buyuk_i_noktasiz_olur():
    assert kucult("ISPARTA") == "ısparta"


def test_noktali_i_noktasiz_i_olur():
    assert kucult("FAİZ") == "faiz"


def test_python_lower_yanlis_yapiyor():
    # Bu testin amacı kendi kodumuzu değil, neden var olduğumuzu göstermek.
    assert "FAİZ".lower() != "faiz"
    assert kucult("FAİZ") == "faiz"


def test_ozel_karakterler_korunuyor():
    assert kucult("TÜFE") == "tüfe"
    assert kucult("ÜRETİCİ") == "üretici"


def test_arama_anahtari_turkce_katliyor():
    assert arama_anahtari("Tüketici Fiyat Endeksi") == "tuketici fiyat endeksi"
    assert arama_anahtari("ÖLÇÜM") == "olcum"


def test_ayni_kelimenin_yazimlari_esitleniyor():
    yazimlar = ["faiz", "FAİZ", "Faiz", "fâiz"]
    anahtarlar = {arama_anahtari(y) for y in yazimlar}
    assert anahtarlar == {"faiz"}


def test_bosluklar_tekleniyor():
    assert arama_anahtari("  politika   faizi \n") == "politika faizi"


def test_bos_metin():
    assert arama_anahtari("") == ""
    assert arama_anahtari("   ") == ""
