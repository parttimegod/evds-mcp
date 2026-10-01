"""ADF sonuçları ve uygulanan dönüşümle birlikte korelasyon raporlar.

Test sonuçları kullanılan örnekleme ve ADF ayarlarına bağlıdır. Dönüşüm
ve gecikme seçimi tek başına iktisadi ilişkiyi veya nedenselliği kanıtlamaz.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from statsmodels.tsa.stattools import adfuller, coint

# Uygulamanın kabul ettiği en kısa test girdisi.
ASGARI_GOZLEM = 20

# Otomatik dönüşüm aramasını üç farkla sınırlıyoruz.
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
    if donusum in ("seviye", "level"):
        return list(x)
    if donusum == "logd1":
        return log_fark(x)
    if donusum.startswith("d") and donusum[1:].isdigit():
        return fark(x, int(donusum[1:]))
    raise AnalizHatasi(f"Bilinmeyen dönüşüm: {donusum!r}")


def duraganlik(x: list[float]) -> Duraganlik:
    """ADF'de birim kök sıfır hipotezini reddeden ilk dönüşümü arar.

    Sabit terim, AIC gecikme seçimi ve %5 eşik kullanılır. Dönen derece
    bu kurala dayalı bir sınıflamadır; kesin bütünleşme derecesi değildir.
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
        notlar.append("Log farkında ADF birim kök hipotezi reddedildi.")
        return Duraganlik(
            derece=1, donusum="logd1", p_degerleri=p, log_yeterli=True, notlar=notlar
        )

    if derece is None:
        notlar.append(
            f"{MAKS_FARK} farka kadar ADF birim kök hipotezi reddedilmedi. "
            "Örneklem, test ayarları ve yapısal kırılmalar ayrıca incelenmeli."
        )
        return Duraganlik(derece=None, donusum="seviye", p_degerleri=p, notlar=notlar)

    if derece >= 2:
        notlar.append(
            f"Bu örneklemde ADF kuralı seriyi I({derece}) olarak sınıfladı. "
            "Tek fark ve log farkında birim kök hipotezi reddedilmedi."
        )
    return Duraganlik(derece=derece, donusum=f"d{derece}", p_degerleri=p, notlar=notlar)


def korelasyon(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    pay = sum((i - ma) * (j - mb) for i, j in zip(a, b, strict=True))
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


def gecikmeli_korelasyon(
    a: list[float],
    b: list[float],
    maks_gecikme: int = 12,
) -> dict:
    """a'nın k dönem önceki değeriyle b'nin korelasyonunu tarar.

    En yüksek mutlak korelasyonu seçer. Bu örneklem içi seçim için
    çoklu karşılaştırma düzeltmesi veya dış örneklem doğrulaması yapılmaz.
    """
    if maks_gecikme < 0:
        raise AnalizHatasi("Gecikme negatif olamaz.")
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    if n - maks_gecikme < ASGARI_GOZLEM:
        raise AnalizHatasi(
            f"{maks_gecikme} gecikme için yeterli gözlem yok ({n} var). "
            "Aralığı genişlet ya da maks_gecikme'yi düşür."
        )

    profil = {}
    for k in range(maks_gecikme + 1):
        x = a[: n - k] if k else a
        y = b[k:]
        m = min(len(x), len(y))
        profil[k] = round(korelasyon(x[:m], y[:m]), 4)

    tepe = max(profil, key=lambda k: abs(profil[k]))
    return {"profil": profil, "tepe_gecikme": tepe, "tepe_korelasyon": profil[tepe]}


def iliski(
    a: list[float],
    b: list[float],
    ad_a: str,
    ad_b: str,
    donusum_zorla: str | None = None,
    maks_gecikme: int = 0,
) -> dict:
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
    dereceler_farkli = da.derece != db.derece
    if dereceler_farkli:
        uyarilar.append(
            f"Bütünleşme dereceleri farklı: {ad_a} I({da.derece}), "
            f"{ad_b} I({db.derece})."
        )

    if donusum_zorla:
        donusum = donusum_zorla
        # Zorlanan dönüşüm durağanlaştırmıyorsa sustuğumuz için değil,
        # söylediğimiz için sorumluluk kullanıcıda olsun.
        for ad, d in ((ad_a, da), (ad_b, db)):
            test_adi = "seviye" if donusum == "level" else donusum
            p = d.p_degerleri.get(test_adi)
            if p is not None and p >= ALFA:
                uyarilar.append(
                    f"{ad}: istenen dönüşüm ({donusum}) için ADF birim kök "
                    f"hipotezi reddedilmedi (p={p:.4f}); durağanlaştırmıyor "
                    "olabilir. Sonuç dikkatle yorumlanmalı."
                )
    else:
        donusum = (
            "logd1" if (ortak == 1 and da.log_yeterli and db.log_yeterli) else f"d{ortak}"
        )
        if dereceler_farkli:
            uyarilar.append(
                f"İkisi de {ortak}. dereceden farklandı; düşük dereceli seri "
                "aşırı farklanmış ve ilişki olduğundan zayıf görünüyor olabilir. "
                "İktisadi olarak anlamlı dönüşümü biliyorsan donusum_zorla ile "
                "ver (yüzde değişim için 'logd1')."
            )

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
                "Bu rakamı tek başına ilişki kanıtı olarak kullanma. "
                "En az bir seride ADF birim kök hipotezi reddedilmedi; "
                "seviye korelasyonu yanıltıcı olabilir."
                if ortak > 0
                else "İki seride de ADF birim kök hipotezi reddedildi. "
                     "Seviye korelasyonu nedensellik veya model uygunluğu "
                     "kanıtı değildir."
            ),
        },
        "yorum": (
            "Bu bir korelasyondur, nedensellik değildir. Nedensel cümle "
            "kurmak için kimlik stratejisi gerekir; Granger testi bile "
            "tek başına yetmez."
        ),
    }

    if maks_gecikme:
        g = gecikmeli_korelasyon(ta, tb, maks_gecikme)
        sonuc["gecikme"] = g
        if g["tepe_gecikme"] > 0:
            uyarilar.append(
                f"En güçlü ilişki {g['tepe_gecikme']}. gecikmede "
                f"({g['tepe_korelasyon']}), eşanlı değil ({sonuc['korelasyon']}). "
                "Bu tepe aynı örneklemde seçildi; ayrıca doğrulanmalı."
            )

    # İki seri de I(1) ise seviyelerde uzun dönem ilişki olabilir.
    if da.derece == db.derece == 1:
        p = esbutunlesme(a, b)
        sonuc["esbutunlesme"] = {
            "p": round(p, 4),
            "sonuc": "var" if p < ALFA else "yok",
            "not": (
                "Bu örneklemde eşbütünleşme yok sıfır hipotezi reddedildi. "
                "Uzun dönem ilişki ve hata düzeltme modeli ayrıca incelenebilir."
                if p < ALFA
                else "Eşbütünleşme yok sıfır hipotezi reddedilmedi; "
                     "bu sonuç tek başına fark modelini doğrulamaz."
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
