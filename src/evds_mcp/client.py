"""EVDS web servisi istemcisi.

Tek endpoint, header'da anahtar, birkaç parametre. Bu yüzden hazır paket
kullanmak yerine kendimiz yazdık -- hata mesajları üzerinde kontrol
istiyoruz, çünkü bu mesajları sonunda bir dil modeli okuyacak.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import httpx

TABAN = "https://evds2.tcmb.gov.tr/service/evds/"

# EVDS frekans kodları. Sadece 5'i canlı doğruladım, gerisi dokümandan --
# bkz. SONRA.md
FREKANS = {
    "günlük": 1,
    "işgünü": 2,
    "haftalık": 3,
    "ayda2": 4,
    "aylık": 5,
    "çeyreklik": 6,
    "6aylık": 7,
    "yıllık": 8,
}


class EVDSHatasi(Exception):
    pass


class AnahtarYok(EVDSHatasi):
    pass


@dataclass(frozen=True)
class Gozlem:
    tarih: str
    deger: float | None


@dataclass(frozen=True)
class Seri:
    kod: str
    gozlemler: list[Gozlem]

    @property
    def dolu_sayisi(self) -> int:
        return sum(1 for g in self.gozlemler if g.deger is not None)


def _tarih_yaz(t: date) -> str:
    # EVDS GG-AA-YYYY istiyor. ISO değil; karıştırılırsa sessizce
    # yanlış aralık gelir, hata dönmez.
    return t.strftime("%d-%m-%Y")


def _sutun_bul(satir: dict, kod: str) -> str | None:
    # İstediğin kod TP.FG.J0, dönen sütun TP_FG_J0 olabiliyor.
    for aday in (kod, kod.replace(".", "_")):
        if aday in satir:
            return aday
    return None


def _sayiya_cevir(ham) -> float | None:
    # Eksik gözlemler boş string ya da None olarak geliyor.
    if ham is None or ham == "":
        return None
    try:
        return float(ham)
    except (TypeError, ValueError):
        return None


class EVDS:
    def __init__(self, anahtar: str | None = None, zaman_asimi: float = 20.0):
        self.anahtar = anahtar or os.environ.get("EVDS_API_KEY", "")
        if not self.anahtar:
            raise AnahtarYok(
                "EVDS API anahtarı yok. evds2.tcmb.gov.tr adresinden ücretsiz "
                "alıp EVDS_API_KEY ortam değişkenine koy."
            )
        self._http = httpx.Client(
            base_url=TABAN,
            headers={"key": self.anahtar},  # 2024'ten beri URL'de değil, header'da
            timeout=zaman_asimi,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EVDS:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def veri(
        self,
        kodlar: list[str],
        baslangic: date,
        bitis: date,
        frekans: str = "aylık",
    ) -> list[Seri]:
        if not kodlar:
            raise EVDSHatasi("En az bir seri kodu gerekli.")
        if baslangic > bitis:
            raise EVDSHatasi(
                f"Başlangıç bitişten sonra: {baslangic} > {bitis}"
            )
        if frekans not in FREKANS:
            raise EVDSHatasi(
                f"Bilinmeyen frekans {frekans!r}. "
                f"Seçenekler: {', '.join(FREKANS)}"
            )

        yanit = self._http.get(
            "",
            params={
                "series": "-".join(kodlar),
                "startDate": _tarih_yaz(baslangic),
                "endDate": _tarih_yaz(bitis),
                "frequency": FREKANS[frekans],
                "type": "json",
            },
        )
        if yanit.status_code == 401:
            raise AnahtarYok("EVDS anahtarı reddedildi. Anahtarı kontrol et.")
        yanit.raise_for_status()

        return self._ayikla(yanit.json(), kodlar)

    @staticmethod
    def _ayikla(govde: dict, kodlar: list[str]) -> list[Seri]:
        satirlar = govde.get("items") or []
        if not satirlar:
            raise EVDSHatasi(
                f"{', '.join(kodlar)} için bu aralıkta gözlem yok. "
                "Kod yanlış olabilir ya da seri bu tarihlerde yayınlanmamış."
            )

        ornek = satirlar[0]
        seriler = []
        for kod in kodlar:
            sutun = _sutun_bul(ornek, kod)
            if sutun is None:
                # Diğer seriler geldiyse onları döndürmek, hepsini
                # birden patlatmaktan iyi.
                seriler.append(Seri(kod=kod, gozlemler=[]))
                continue
            seriler.append(
                Seri(
                    kod=kod,
                    gozlemler=[
                        Gozlem(
                            tarih=str(s.get("Tarih", "")),
                            deger=_sayiya_cevir(s.get(sutun)),
                        )
                        for s in satirlar
                    ],
                )
            )
        return seriler
