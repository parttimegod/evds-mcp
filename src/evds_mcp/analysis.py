"""Durağanlık testleri ve ilişki analizi.

Buranın amacı hesap yapmak değil, yanlış hesabı imkânsız kılmak.

Gerekçesi ASAMA2.md'de ölçülerek yazıldı: TÜFE ve politika faizi
seviyelerinde korelasyon 0.863 çıkıyor, ikisi de durağan olmadığı için
bu sahte. Fark alınınca 0.158. Bir dil modeli aradaki farkı kendiliğinden
görmüyor -- o yüzden ham korelasyonu hesaplayan bir araç sunmuyoruz.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from statsmodels.tsa.stattools import adfuller, coint

# ADF için makul bir alt sınır. Altında test anlamsız.
ASGARI_GOZLEM = 20

# Fark almanın da bir sınırı var; I(3) gerçek veride neredeyse yok,
# oraya geliyorsak muhtemelen seri bozuk.
MAKS_FARK = 3

ALFA = 0.05


class AnalizHatasi(Exception):
    pass


@dataclass
class Duraganlik:
    derece: int | None            # I(d); None ise MAKS_FARK'a kadar durağanlaşmadı
    donusum: str                  # "seviye", "d1", "d2", "logd1" ...
    p_degerleri: dict[str, float] = field(default_factory=dict)
    log_yeterli: bool = False     # log farkı tek başına durağan mı
    notlar: list[str] = field(default_factory=list)


def _adf_p(x: list[float]) -> float:
    if len(x) < ASGARI_GOZLEM:
        raise AnalizHatasi(
            f"ADF için en az {ASGARI_GOZLEM} gözlem gerekiyor, {len(x)} var. "
            "Tarih aralığını genişlet."
        )
    return float(adfuller(x, autolag="AIC")[1])


def fark(x: list[float], derece: int = 1) -> list[float]:
    for _ in range(derece):
        x = [x[i] - x[i - 1] for i in range(1, len(x))]
    return x


def log_fark(x: list[float]) -> list[float]:
    if any(v <= 0 for v in x):
        raise AnalizHatasi("Log farkı için bütün değerler pozitif olmalı.")
    return [math.log(x[i] / x[i - 1]) for i in range(1, len(x))]


def donustur(x: list[float], donusum: str) -> list[float]:
    if donusum == "seviye":
        return list(x)
    if donusum == "logd1":
        return log_fark(x)
    if donusum.startswith("d") and donusum[1:].isdigit():
        return fark(x, int(donusum[1:]))
    raise AnalizHatasi(f"Bilinmeyen dönüşüm: {donusum!r}")


def duraganlik(x: list[float]) -> Duraganlik:
    """Seriyi durağanlaştıran en düşük dereceli dönüşümü bulur.

    Fark derecesini varsaymıyoruz, ölçüyoruz. ASAMA2.md'deki ölçüme göre
    Türkiye TÜFE'si bu dönemde I(2) -- yani "fiyat endeksinde bir log
    farkı al" ezberi burada yanlış sonuç veriyor.
    """
    p = {}
    notlar: list[str] = []

    p["seviye"] = _adf_p(x)
    if p["seviye"] < ALFA:
        return Duraganlik(derece=0, donusum="seviye", p_degerleri=p)

    # Log farkı yüzde değişim demek; durağansa yorumu en kolay dönüşüm bu.
    log_yeterli = False
    if all(v > 0 for v in x):
        try:
            p["logd1"] = _adf_p(log_fark(x))
            log_yeterli = p["logd1"] < ALFA
        except AnalizHatasi:
            pass

    derece = None
    for d in range(1, MAKS_FARK + 1):
        p[f"d{d}"] = _adf_p(fark(x, d))
        if p[f"d{d}"] < ALFA:
            derece = d
            break

    if log_yeterli and (derece is None or derece >= 1):
        notlar.append("Log farkı durağan; yüzde değişim olarak yorumlanabilir.")
        return Duraganlik(
            derece=1, donusum="logd1", p_degerleri=p, log_yeterli=True, notlar=notlar
        )

    if derece is None:
        notlar.append(
            f"{MAKS_FARK} farka kadar durağanlaşmadı. Seride yapısal kırılma "
            "olabilir; ADF kırılmayı birim kök sanar."
        )
        return Duraganlik(derece=None, donusum="seviye", p_degerleri=p, notlar=notlar)

    if derece >= 2:
        notlar.append(
            f"Seri I({derece}). Tek fark ya da log farkı yetmiyor -- "
            "standart 'log farkı al' kuralı bu seride yanlış sonuç verir."
        )
    return Duraganlik(derece=derece, donusum=f"d{derece}", p_degerleri=p, notlar=notlar)


def korelasyon(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    pay = sum((i - ma) * (j - mb) for i, j in zip(a, b))
    payda = math.sqrt(
        sum((i - ma) ** 2 for i in a) * sum((j - mb) ** 2 for j in b)
    )
    if payda == 0:
        raise AnalizHatasi("Serilerden biri sabit; korelasyon tanımsız.")
    return pay / payda


def esbutunlesme(a: list[float], b: list[float]) -> float:
    """Engle-Granger. H0 = eşbütünleşme yok."""
    n = min(len(a), len(b))
    return float(coint(a[-n:], b[-n:])[1])


def iliski(a: list[float], b: list[float], ad_a: str, ad_b: str) -> dict:
    """İki seri arasındaki ilişkiyi metodolojik kontrollerden geçirerek verir.

    Ham seviye korelasyonu da dönüyor ama açıkça "kullanma" etiketiyle --
    çünkü model onu başka türlü hesaplayıp raporlayabilir; yanında
    neden yanlış olduğu yazsın.
    """
    da, db = duraganlik(a), duraganlik(b)
    uyarilar: list[str] = []

    if da.derece is None or db.derece is None:
        raise AnalizHatasi(
            f"{ad_a if da.derece is None else ad_b} {MAKS_FARK} farka kadar "
            "durağanlaşmıyor. Bu seriyle korelasyon raporlanamaz."
        )

    ortak = max(da.derece, db.derece)
    if da.derece != db.derece:
        uyarilar.append(
            f"Bütünleşme dereceleri farklı: {ad_a} I({da.derece}), "
            f"{ad_b} I({db.derece}). Her ikisi de {ortak}. dereceden "
            "farklandı; düşük dereceli seri aşırı farklanmış olabilir."
        )

    donusum = "logd1" if (ortak == 1 and da.log_yeterli and db.log_yeterli) else f"d{ortak}"
    ta, tb = donustur(a, donusum), donustur(b, donusum)

    sonuc = {
        "donusum": donusum,
        "korelasyon": round(korelasyon(ta, tb), 4),
        "gozlem": min(len(ta), len(tb)),
        "duraganlik": {
            ad_a: {"derece": da.derece, "p": _yuvarla(da.p_degerleri)},
            ad_b: {"derece": db.derece, "p": _yuvarla(db.p_degerleri)},
        },
        "ham_seviye_korelasyonu": {
            "deger": round(korelasyon(a, b), 4),
            "uyari": (
                "Bu rakamı kullanma. Seriler durağan olmadığı için sahte "
                "regresyon; ortak trend yüzünden şişkin çıkıyor."
            ),
        },
        "yorum": (
            "Bu bir korelasyondur, nedensellik değildir. Nedensel cümle "
            "kurmak için kimlik stratejisi gerekir; Granger testi bile "
            "tek başına yetmez."
        ),
    }

    # İki seri de I(1) ise seviyelerde uzun dönem ilişki olabilir.
    if da.derece == db.derece == 1:
        p = esbutunlesme(a, b)
        sonuc["esbutunlesme"] = {
            "p": round(p, 4),
            "sonuc": "var" if p < ALFA else "yok",
            "not": (
                "Eşbütünleşme varsa seviyelerde uzun dönem ilişki vardır ve "
                "hata düzeltme modeli kurulmalı; sadece farklarla çalışmak "
                "uzun dönem bilgisini atar."
                if p < ALFA
                else "Eşbütünleşme bulunamadı; farklarla çalışmak doğru."
            ),
        }

    # Notlar seri bazlı; hangisine ait olduğu yazmazsa kafa karıştırıyor.
    uyarilar += [f"{ad_a}: {n}" for n in da.notlar]
    uyarilar += [f"{ad_b}: {n}" for n in db.notlar]
    if uyarilar:
        sonuc["uyarilar"] = uyarilar
    return sonuc


def _yuvarla(d: dict[str, float]) -> dict[str, float]:
    return {k: round(v, 4) for k, v in d.items()}
