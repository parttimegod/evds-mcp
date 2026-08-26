"""Türkçe metin normalizasyonu.

Python'un str.lower() metodu Türkçe için yanlış çalışıyor:

    "I".lower()   -> "i"    (olması gereken: "ı")
    "İ".lower()   -> "i̇"    (i + U+0307, tek karakter değil)

Bu, seri adlarında sessiz hataya yol açıyor. "FAİZ" ile "faiz"
eşleşmiyor ve hata da almıyorsun, sadece sonuç dönmüyor.
"""

import unicodedata

# Türkçe karakterleri ASCII karşılıklarına indirger. Amaç, kullanıcının
# "olcum" yazıp "ölçüm" bulabilmesi -- ki insanlar genelde böyle yazıyor.
_KATLAMA = str.maketrans(
    {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "â": "a",
        "î": "i",
        "û": "u",
    }
)


def kucult(metin: str) -> str:
    """Türkçe kurallarına göre küçük harfe çevirir.

    İ -> i, I -> ı. Bunları lower() öncesi elle değiştirmek gerekiyor,
    çünkü lower() Türkçe bilmiyor.
    """
    metin = unicodedata.normalize("NFC", metin)
    return metin.replace("İ", "i").replace("I", "ı").lower()


def arama_anahtari(metin: str) -> str:
    """Aramada karşılaştırma için kullanılacak anahtarı üretir.

    Küçült, Türkçe karakterleri katla, kalan birleşik işaretleri at,
    boşlukları tekle. Arama tarafında hem sorgu hem de seri adı
    bu fonksiyondan geçirilir.
    """
    metin = kucult(metin)
    metin = metin.translate(_KATLAMA)

    # Katlamadan kaçan aksanlar için (ör. dışarıdan gelen "é")
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(k for k in metin if not unicodedata.combining(k))

    return " ".join(metin.split())
