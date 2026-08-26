"""MCP sunucusu.

Bu katman ince olmalı: iş mantığı client.py ve catalog.py'de. Buradaki
asıl emek docstring'lerde, çünkü onlar dokümantasyon değil -- modelin
hangi aracı ne zaman çağıracağına karar verirken okuduğu metin.

Araç adları ve parametreler İngilizce, açıklamalar iki dilli. Model
"enflasyon" da yazsa "inflation" da yazsa aynı yere gitsin diye.
"""

from __future__ import annotations

import statistics
from datetime import date, datetime

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .catalog import Katalog
from .client import EVDS, FREKANS, EVDSHatasi

# Bir seri 2003'ten beri aylıksa 280 gözlem eder. Üç seri istendiğinde
# bağlam penceresi sayıyla doluyor ve model düzgün düşünemiyor. Bu yüzden
# varsayılan pencere dar; tamamı ancak açıkça istenince geliyor.
PENCERE = 24

mcp = FastMCP(
    name="evds",
    instructions=(
        "TCMB EVDS'deki Türkiye makroekonomik verisine erişim.\n\n"
        "Sıra şöyle: seri kodları anlaşılmaz olduğu için (TP.FG.J0 gibi) "
        "önce search_series ile aradığın kavramı ara, dönen koddan birini "
        "seç, sonra summarize_series ile bak ya da get_series ile veriyi al.\n\n"
        "Kod uydurma. Emin değilsen search_series çağır."
    ),
)

_evds: EVDS | None = None
_katalog: Katalog | None = None


def _baglan() -> tuple[EVDS, Katalog]:
    global _evds, _katalog
    if _evds is None:
        _evds = EVDS()
        _katalog = Katalog(_evds)
    return _evds, _katalog


def _tarih_oku(metin: str, alan: str) -> date:
    for kalip in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(metin, kalip).date()
        except ValueError:
            continue
    raise ToolError(
        f"{alan} tarihi anlaşılmadı: {metin!r}. "
        "YYYY-AA-GG kullan (örnek: 2020-01-01). Yıl ya da yıl-ay da olur."
    )


def _ozet(gozlemler) -> dict:
    dolu = [g.deger for g in gozlemler if g.deger is not None]
    if not dolu:
        return {"gozlem": len(gozlemler), "eksik": len(gozlemler), "not": "Hiç dolu gözlem yok."}

    ilk, son = dolu[0], dolu[-1]
    ozet = {
        "gozlem": len(gozlemler),
        "eksik": len(gozlemler) - len(dolu),
        "ilk_tarih": gozlemler[0].tarih,
        "son_tarih": gozlemler[-1].tarih,
        "ilk": ilk,
        "son": son,
        "min": min(dolu),
        "max": max(dolu),
        "ortalama": round(statistics.fmean(dolu), 4),
    }
    if ilk:
        ozet["toplam_degisim_yuzde"] = round((son - ilk) / abs(ilk) * 100, 2)
    return ozet


def _kunye(s) -> dict:
    return {
        "kod": s.kod,
        "ad": s.ad,
        "ad_eng": s.ad_eng,
        "grup": s.grup_kodu,
        "frekans": s.frekans,
        "kaynak": s.kaynak,
        "kapsam": f"{s.baslangic} - {s.bitis}",
        "varsayilan_toplama": s.toplama,
    }


@mcp.tool
def search_series(query: str, limit: int = 10) -> dict:
    """EVDS'de seri arar. Her iş buradan başlar.

    Türkçe ya da İngilizce kavram yaz: "enflasyon", "işsizlik", "policy
    rate", "konut fiyat endeksi", "cari açık", "döviz kuru". Seri
    kodlarını (TP.FG.J0 gibi) kimse ezbere bilmez, o yüzden koddan değil
    kavramdan başla.

    Dönen her kayıtta seri kodu, adı, frekansı ve hangi tarihler arasında
    veri olduğu var. Kapsama bak: EVDS'de yayını durmuş çok sayıda arşiv
    serisi var, onlardan güncel veri gelmez.

    Args:
        query: Aranan kavram. Tek kelime de olur, birkaç kelime de.
        limit: En fazla kaç seri dönsün.
    """
    _, katalog = _baglan()
    try:
        gruplar = katalog.grup_ara(query, limit=3)
    except EVDSHatasi as e:
        raise ToolError(str(e)) from e

    if not gruplar:
        raise ToolError(
            f"{query!r} için sonuç yok. Daha genel bir kelime dene "
            "(örnek: 'işsizlik' yerine 'işgücü', 'büyüme' yerine 'GSYH')."
        )

    # Gruplar puan sırasında; her birine kota koyuyoruz ki kalabalık bir
    # grup (IMF'nin ülke ülke TÜFE'si gibi) sonuçları doldurmasın.
    kota = max(2, limit // len(gruplar))
    bulunan = []
    for g in gruplar:
        try:
            bulunan.extend(katalog.seri_ara(query, g.kod, limit=kota))
        except EVDSHatasi:
            continue  # boş grup; diğerleri işe yarayabilir

    if not bulunan:
        # Grup bulundu ama içinde eşleşen seri yok. Grupları göster ki
        # model bir sonraki adımı bilsin.
        return {
            "seriler": [],
            "aday_gruplar": [{"kod": g.kod, "ad": g.ad} for g in gruplar],
            "not": (
                "Sorguyla eşleşen seri çıkmadı ama yukarıdaki gruplar konuyla "
                "ilgili. Daha genel bir kelimeyle tekrar ara."
            ),
        }

    return {
        "seriler": [_kunye(s) for s in bulunan[:limit]],
        "not": "Kodu seçtikten sonra summarize_series ya da get_series çağır.",
    }


@mcp.tool
def summarize_series(
    code: str,
    start: str,
    end: str,
    frequency: str = "aylık",
) -> dict:
    """Bir seriye ham veriyi dökmeden bakar.

    Gözlem sayısı, eksik veri, ilk/son değer, min, max, ortalama ve
    toplam değişim döner. Seriyi tanımak, iki seriyi karşılaştırmadan
    önce büyüklük mertebesini görmek ya da veri var mı diye yoklamak
    için bunu kullan -- get_series'ten çok daha ucuz.

    Args:
        code: Seri kodu (search_series'ten gelir).
        start: Başlangıç, YYYY-AA-GG.
        end: Bitiş, YYYY-AA-GG.
        frequency: günlük, işgünü, haftalık, ayda2, aylık, çeyreklik,
            6aylık, yıllık.
    """
    evds, _ = _baglan()
    b, s = _tarih_oku(start, "start"), _tarih_oku(end, "end")
    try:
        (seri,) = evds.veri([code], b, s, frekans=_frekans_dogrula(frequency))
    except EVDSHatasi as e:
        raise ToolError(str(e)) from e

    return {"kod": code, "frekans": frequency, "ozet": _ozet(seri.gozlemler)}


@mcp.tool
def get_series(
    codes: list[str],
    start: str,
    end: str,
    frequency: str = "aylık",
    full: bool = False,
) -> dict:
    """Seri verisini getirir. Birden fazla kod verilebilir.

    Varsayılan olarak özet ve son gözlemler döner, tamamı değil -- uzun
    seriler bağlamı doldurup akıl yürütmeyi bozuyor. Bütün gözlemlere
    gerçekten ihtiyacın varsa (grafik, regresyon, dönüm noktası araması)
    full=True ver.

    Birden fazla seriyi tek çağrıda istemek, ayrı ayrı istemekten iyi:
    aynı tarih ızgarasına hizalı gelirler.

    Args:
        codes: Seri kodları. Örnek: ["TP.FG.J0", "TP.APIFON4"].
        start: Başlangıç, YYYY-AA-GG.
        end: Bitiş, YYYY-AA-GG.
        frequency: günlük, işgünü, haftalık, ayda2, aylık, çeyreklik,
            6aylık, yıllık.
        full: True ise bütün gözlemler döner.
    """
    evds, _ = _baglan()
    if not codes:
        raise ToolError("En az bir seri kodu gerekli. Kod için search_series çağır.")

    b, s = _tarih_oku(start, "start"), _tarih_oku(end, "end")
    try:
        seriler = evds.veri(codes, b, s, frekans=_frekans_dogrula(frequency))
    except EVDSHatasi as e:
        raise ToolError(str(e)) from e

    cikti = []
    kirpildi = False
    for seri in seriler:
        gozlemler = seri.gozlemler
        if not gozlemler:
            cikti.append(
                {
                    "kod": seri.kod,
                    "veri": [],
                    "not": "Bu kod için veri gelmedi. Kodu search_series ile doğrula.",
                }
            )
            continue

        gosterilen = gozlemler if full else gozlemler[-PENCERE:]
        kirpildi = kirpildi or len(gosterilen) < len(gozlemler)
        cikti.append(
            {
                "kod": seri.kod,
                "ozet": _ozet(gozlemler),
                "veri": [{"tarih": g.tarih, "deger": g.deger} for g in gosterilen],
            }
        )

    sonuc = {"frekans": frequency, "seriler": cikti}
    if kirpildi:
        sonuc["kirpildi"] = True
        sonuc["not"] = (
            f"Son {PENCERE} gözlem gösteriliyor; özetler serinin tamamını "
            "kapsıyor. Hepsi için full=True ver."
        )
    return sonuc


def _frekans_dogrula(frekans: str) -> str:
    if frekans not in FREKANS:
        raise ToolError(
            f"Bilinmeyen frekans {frekans!r}. Seçenekler: {', '.join(FREKANS)}"
        )
    return frekans


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
