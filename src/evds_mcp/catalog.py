"""Seri kataloğu ve arama.

EVDS'de seri kodları anlaşılmaz (`TP.FG.J0`), o yüzden her oturum
aramayla başlıyor. Aramanın kalitesi bu paketin kalitesi.

Toplu seri ucu yok: 676 veri grubu var ve gruptaki serileri ancak
grup kodu vererek çekebiliyorsunuz. Hepsini indirmek 676 istek eder.
Bu yüzden arama iki seviyeli:

    grup_ara("enflasyon")  ->  aday veri grupları      (1 istek, sonra bellekte)
    seri_ara("tufe", grup) ->  gruptaki seriler        (grup başına 1 istek)
"""

from __future__ import annotations

from dataclasses import dataclass

from .client import EVDS, EVDSHatasi
from .text import arama_anahtari


@dataclass(frozen=True)
class Grup:
    kod: str
    ad: str
    ad_eng: str
    frekans: str
    kaynak: str

    @property
    def _aranacak(self) -> str:
        return arama_anahtari(f"{self.ad} {self.ad_eng}")


@dataclass(frozen=True)
class SeriKunye:
    kod: str
    ad: str
    ad_eng: str
    grup_kodu: str
    frekans: str
    kaynak: str
    toplama: str
    baslangic: str
    bitis: str
    sira: int          # EVDS'nin kendi ekran sirasi; bassliklar once geliyor

    @property
    def _aranacak(self) -> str:
        return arama_anahtari(f"{self.ad} {self.ad_eng}")


# İnsanın kullandığı kelimeyle verinin kullandığı kelime hep tutmuyor:
# kimse "işsizlik" aradığında "Temel İşgücü Göstergeleri" yazmıyor.
# Aşağıdakiler tahminle değil ölçerek eklendi -- bu sorgular sözlük
# olmadan sıfır sonuç döndürüyordu. Genişi SONRA.md'de.
ESANLAMLI = {
    "issizlik": ["isgucu", "istihdam"],
    "issiz": ["isgucu", "istihdam"],
    "buyume": ["hasila", "gsyh"],
    "gsyh": ["hasila"],
    "enflasyon": ["tuketici fiyat endeksi"],  # "enflasyon" diyen TUFE kastediyor
    "tufe": ["tuketici fiyat endeksi"],
    "ufe": ["uretici fiyat endeksi"],
    "cari acik": ["cari islemler", "odemeler dengesi"],
    "cari denge": ["cari islemler", "odemeler dengesi"],
    # Nominal kur grubunun adi sadece "Doviz Kurlari"; icinde "dolar"
    # gecmiyor. Oysa EVDS'nin en cok istenen serisi orada.
    "dolar": ["doviz kurlari"],
    "usd": ["doviz kurlari"],
    "euro": ["doviz kurlari"],
    "avro": ["doviz kurlari"],
    "kur": ["doviz kurlari"],
    # Grup adlarinin Ingilizcesi de aranıyor ama kullanicinin kelimesi
    # yine tutmuyor: "dollar" arayan "Exchange Rates"i bulamiyor.
    "dollar": ["exchange rates", "doviz kurlari"],
    "inflation": ["consumer price index", "tuketici fiyat endeksi"],
    "cpi": ["consumer price index"],
    "unemployment": ["labour force", "labor force", "isgucu"],
    "employment": ["labour force", "labor force", "isgucu"],
    "growth": ["gross domestic product", "hasila"],
    "gdp": ["gross domestic product", "hasila"],
    "policy rate": ["policy interest rate"],
    "current account": ["balance of payments", "odemeler dengesi"],
}

# Önek eşleşmesi bunun altındaki kelimelerde yapılmıyor; "kur" gibi kısa
# kökler "kurum", "kuruluş" gibi alakasız kelimeleri yakalıyor.
ASGARI_KOK = 4


def _genislet(sorgu: str) -> str:
    """Sorguya eşanlamlılarını ekler.

    Türkçe eklemeli bir dil: "dolar" ile "doları" tam eşleşmiyor. Ekler
    sona geldiği için sözlük anahtarını önek olarak arıyoruz -- kaba ama
    bu boyutta bir sözlük için gövdeleyiciden daha az sürprizli.
    """
    parcalar = [sorgu]
    parcalar += ESANLAMLI.get(sorgu, [])
    for kelime in sorgu.split():
        if kelime in ESANLAMLI:
            parcalar += ESANLAMLI[kelime]
            continue
        for kok, karsilik in ESANLAMLI.items():
            if len(kok) >= ASGARI_KOK and " " not in kok and kelime.startswith(kok):
                parcalar += karsilik
                break
    return " ".join(parcalar)


def _puan(sorgu: str, hedef: str) -> int:
    """Sorgudaki her kelime için hedefe bakar.

    Tam kelime eşleşmesi 2, kelime içinde geçmesi 1 puan. Bütün
    kelimelerin bulunmasını şart koşmuyoruz -- "cari acik" sorgusu
    "Cari İşlemler Dengesi"i bulamazdı, çünkü "açık" adda geçmiyor.
    """
    kelimeler = hedef.split()
    toplam = 0
    for k in sorgu.split():
        if k in kelimeler:
            toplam += 2
        elif k in hedef:
            toplam += 1
    return toplam


def _arsiv_mi(ad: str) -> bool:
    return "arsiv" in arama_anahtari(ad)


def _turkiye_mi(kunye) -> bool:
    """Uluslararası karşılaştırma gruplarında Türkiye'yi öne almak için.

    IMF ve BIS grupları ülkeleri alfabetik diziyor; "politika faizi"
    araması Almanya'yı getirip Türkiye'yi 470. sıraya gömüyordu. Türkiye
    verisi için yazılmış bir arayüzde bu kabul edilebilir değil.
    """
    return kunye.kod.upper().endswith(".TUR") or "turkiye" in arama_anahtari(kunye.ad)


def _sirala(adaylar, sorgu: str, limit: int):
    a = arama_anahtari(sorgu)
    if not a:
        raise EVDSHatasi("Arama sorgusu boş.")
    a = _genislet(a)

    puanli = [(_puan(a, x._aranacak), x) for x in adaylar]
    puanli = [(p, x) for p, x in puanli if p > 0]
    # Eşit puanda kısa ad daha spesifik demek, onu öne al. Arşivlenmiş
    # seriler genelde aranan şey değil, geriye at.
    puanli.sort(key=lambda t: (-t[0], _arsiv_mi(t[1].ad), len(t[1].ad)))
    return [x for _, x in puanli[:limit]]


class Katalog:
    """Grup listesini bir kez çekip bellekte tutar.

    Diske önbellek yok, süreç boyunca yaşıyor -- bkz. SONRA.md
    """

    def __init__(self, evds: EVDS):
        self._evds = evds
        self._gruplar: list[Grup] | None = None

    def gruplar(self) -> list[Grup]:
        if self._gruplar is None:
            self._gruplar = [_grup_yap(h) for h in self._evds.veri_gruplari()]
        return self._gruplar

    def grup_ara(self, sorgu: str, limit: int = 10) -> list[Grup]:
        return _sirala(self.gruplar(), sorgu, limit)

    def grup_serileri(self, grup_kodu: str) -> list[SeriKunye]:
        ham = self._evds.grup_serileri(grup_kodu)
        if not ham:
            raise EVDSHatasi(
                f"{grup_kodu!r} grubunda seri yok. Grup kodu yanlış olabilir; "
                "grup_ara ile doğrusunu bul."
            )
        return [_seri_yap(h) for h in ham]

    def seri_ara(self, sorgu: str, grup_kodu: str, limit: int = 20) -> list[SeriKunye]:
        """Gruptaki serileri sorguya göre sıralar ama elemez.

        Elemek işe yaramıyor: grup adı "Tüketici Fiyat Endeksi" olsa da
        içindeki seriler "Genel Endeks", "Gıda ve alkolsüz içecekler"
        diye geçiyor, sorgu kelimesi hiçbirinde yok. Grup zaten eşleştiği
        için doğru yerdeyiz -- eşleşen seri varsa öne al, yoksa EVDS'nin
        kendi ekran sırasına düş. Baslık seriler orada zaten önde.
        """
        seriler = self.grup_serileri(grup_kodu)
        a = _genislet(arama_anahtari(sorgu)) if sorgu else ""
        seriler.sort(
            key=lambda s: (
                -_puan(a, s._aranacak) if a else 0,
                not _turkiye_mi(s),
                _arsiv_mi(s.ad),
                s.sira,
            )
        )
        return seriler[:limit]


def _metin(ham: dict, *anahtarlar: str) -> str:
    for a in anahtarlar:
        d = ham.get(a)
        if d:
            return str(d).strip()
    return ""


def _grup_yap(ham: dict) -> Grup:
    return Grup(
        kod=_metin(ham, "DATAGROUP_CODE"),
        ad=_metin(ham, "DATAGROUP_NAME"),
        ad_eng=_metin(ham, "DATAGROUP_NAME_ENG"),
        frekans=_metin(ham, "FREQUENCY_STR"),
        kaynak=_metin(ham, "DATASOURCE", "DATASOURCE_ENG"),
    )


def _seri_yap(ham: dict) -> SeriKunye:
    return SeriKunye(
        kod=_metin(ham, "SERIE_CODE"),
        ad=_metin(ham, "SERIE_NAME"),
        ad_eng=_metin(ham, "SERIE_NAME_ENG"),
        grup_kodu=_metin(ham, "DATAGROUP_CODE"),
        frekans=_metin(ham, "FREQUENCY_STR"),
        kaynak=_metin(ham, "DATASOURCE", "DATASOURCE_ENG"),
        toplama=_metin(ham, "DEFAULT_AGG_METHOD"),
        # Kapsamı künyede vermek, veriyi çekip "gözlem yok" hatası
        # almaktan iyi. Arşivlenmiş seriler buradan belli oluyor.
        baslangic=_metin(ham, "START_DATE"),
        bitis=_metin(ham, "END_DATE"),
        sira=int(ham.get("SCREEN_ORDER") or 9999),
    )
