"""EVDS web servisi istemcisi.

Hazır paket yerine kendimiz yazdık; hata mesajları üzerinde kontrol
istiyoruz, çünkü bu mesajları sonunda bir dil modeli okuyacak.

Servisin iki tuhaflığı var, ikisi de aşağıda ele alınıyor: parametreler
soru işareti olmadan doğrudan yola ekleniyor, ve dönen sütun adlarında
nokta yerine alt çizgi oluyor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import httpx

# evds2 2026'da evds3'e taşındı ve servis yolu da değişti. Eski
# dokümanlardaki evds2.tcmb.gov.tr/service/evds/ artık arayüze yönlendiriyor.
TABAN = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"

# Sadece 5 (aylık) canlı doğrulandı, gerisi dokümandan -- bkz. SONRA.md
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
    # GG-AA-YYYY. ISO değil; karıştırılırsa API hata vermiyor,
    # sessizce başka aralık dönüyor.
    return t.strftime("%d-%m-%Y")


def _parametre_yaz(**kwargs) -> str:
    # EVDS parametreleri soru işareti olmadan yola ekliyor:
    #   .../igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2020&type=json
    # httpx'in params= parametresi başa "?" koyduğu için elle kuruyoruz.
    # Boş string'i atmıyoruz: datagroups ucu "code=" parametresini
    # boş da olsa görmek istiyor.
    return "&".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)


def _sutun_bul(satir: dict, kod: str) -> str | None:
    # TP.FG.J0 istiyorsun, TP_FG_J0 geliyor.
    for aday in (kod, kod.replace(".", "_")):
        if aday in satir:
            return aday
    return None


def _sayiya_cevir(ham) -> float | None:
    # Eksik gözlemler boş string ya da None. Dolu olanlar "446.45000000"
    # gibi string geliyor.
    if ham is None or ham == "":
        return None
    try:
        return float(ham)
    except (TypeError, ValueError):
        return None


class EVDS:
    def __init__(self, anahtar: str | None = None, zaman_asimi: float = 30.0):
        self.anahtar = anahtar or os.environ.get("EVDS_API_KEY", "")
        if not self.anahtar:
            raise AnahtarYok(
                "EVDS API anahtarı yok. evds3.tcmb.gov.tr adresinden ücretsiz "
                "alıp EVDS_API_KEY ortam değişkenine koy."
            )
        self._http = httpx.Client(
            base_url=TABAN,
            headers={"key": self.anahtar},  # 2024'ten beri URL'de değil
            timeout=zaman_asimi,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EVDS:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _al(self, yol: str):
        yanit = self._http.get(yol)
        if yanit.status_code == 401:
            raise AnahtarYok("EVDS anahtarı reddedildi. Anahtarı kontrol et.")
        yanit.raise_for_status()
        if "json" not in yanit.headers.get("content-type", ""):
            # Yol yanlışsa servis JSON yerine arayüzün HTML'ini döndürüyor.
            raise EVDSHatasi(
                f"JSON beklenirken HTML geldi ({yol!r}). Servis yolu değişmiş olabilir."
            )
        return yanit.json()

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
            raise EVDSHatasi(f"Başlangıç bitişten sonra: {baslangic} > {bitis}")
        if frekans not in FREKANS:
            raise EVDSHatasi(
                f"Bilinmeyen frekans {frekans!r}. Seçenekler: {', '.join(FREKANS)}"
            )

        govde = self._al(
            _parametre_yaz(
                series="-".join(kodlar),
                startDate=_tarih_yaz(baslangic),
                endDate=_tarih_yaz(bitis),
                frequency=FREKANS[frekans],
                type="json",
            )
        )
        return self._ayikla(govde, kodlar)

    def veri_gruplari(self) -> list[dict]:
        """Tüm veri gruplarının künyesi. Katalogun üst seviyesi."""
        return self._al("datagroups/" + _parametre_yaz(mode=0, code="", type="json"))

    def grup_serileri(self, grup_kodu: str) -> list[dict]:
        """Bir veri grubundaki serilerin künyesi."""
        return self._al("serieList/" + _parametre_yaz(type="json", code=grup_kodu))

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
                # Bir kod yanlışsa tüm çağrıyı patlatmak yerine o seriyi
                # boş bırak; diğerleri işe yarayabilir.
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
