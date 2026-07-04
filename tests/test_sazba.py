"""Testy A5 fit-checku (M4). Reálný render vyžaduje GTK; logika se testuje
s injektovaným fake measurerem."""

import re

from honbicka.modely import Karta, TypUzlu
from honbicka.validatory.sazba import (
    SazbaNedostupna,
    _weasy_measurer,
    fit_check_karty,
    limit_mm,
    sirka_obsahu_mm,
    vyuzitelna_vyska_mm,
)


def measurer_dle_delky(html: str, sirka: float) -> float:
    """Fake: výška ~ délce textu (≈45 znaků/řádek, 5 mm/řádek)."""
    text = re.sub(r"<[^>]+>", "", html)
    return len(text) / 45.0 * 5.0


def _karta(atmosfera="A" * 300, predni="P" * 200, zadni="Z" * 200, zadni_30=None):
    return Karta(cislo=1, nazev="Test", typ=TypUzlu.POSTAVA,
                 atmosfera=atmosfera, predni=predni, zadni=zadni, zadni_30=zadni_30)


def test_geometrie_a5():
    assert sirka_obsahu_mm() == 128.0
    assert vyuzitelna_vyska_mm() == 170.0
    assert limit_mm() == 163.2  # 170 × 0,96


def test_kratka_karta_sedne():
    fits = fit_check_karty(_karta(), measurer=measurer_dle_delky)
    assert len(fits) == 2  # predni + zadni (zadni_30 None)
    assert all(f.verdikt for f in fits)


def test_dlouha_karta_pretece():
    fits = fit_check_karty(_karta(atmosfera="A" * 3000), measurer=measurer_dle_delky)
    predni = next(f for f in fits if f.strana == "predni")
    assert not predni.verdikt
    assert predni.vyska_mm > predni.limit_mm


def test_zadni_30_se_kontroluje_kdyz_je():
    fits = fit_check_karty(_karta(zadni_30="X" * 100), measurer=measurer_dle_delky)
    strany = {f.strana for f in fits}
    assert strany == {"predni", "zadni", "zadni_30"}


def test_default_measurer_vyzaduje_gtk_nebo_renderuje():
    # Bez GTK → tvrdá chyba (spec §12: nikdy neodhaduj); s GTK → reálná výška.
    try:
        vyska = _weasy_measurer("<p>ahoj</p>", 128.0)
        assert vyska > 0
    except SazbaNedostupna:
        pass  # očekávané prostředí bez GTK
