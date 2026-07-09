"""Testy A5 fit-checku (M4). Reálný render vyžaduje GTK; logika se testuje
s injektovaným fake measurerem."""

import re

from honbicka.modely import Karta, TypUzlu, Volba
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


def _karta(atmosfera="A" * 300, uvod="P" * 200, zaver="Z" * 200, se_side_volbou=False):
    volby = [Volba(text="Pokračuj", vysledek="Cesta vede dál", cil=2)]
    if se_side_volbou:
        volby.append(Volba(text="Odbočka", vysledek="Vedlejší cesta", cil=3, side=True))
    return Karta(cislo=1, nazev="Test", typ=TypUzlu.POSTAVA,
                 atmosfera=atmosfera, uvod=uvod, zaver=zaver, volby=volby)


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


def test_zadni_30_se_kontroluje_kdyz_ma_side_volbu():
    # zadni_30 existuje (a kontroluje se) právě když karta má SIDE volbu
    fits = fit_check_karty(_karta(se_side_volbou=True), measurer=measurer_dle_delky)
    strany = {f.strana for f in fits}
    assert strany == {"predni", "zadni", "zadni_30"}


def test_default_measurer_vyzaduje_gtk_nebo_renderuje():
    # Bez GTK → tvrdá chyba (spec §12: nikdy neodhaduj); s GTK → reálná výška.
    try:
        vyska = _weasy_measurer("<p>ahoj</p>", 128.0)
        assert vyska > 0
    except SazbaNedostupna:
        pass  # očekávané prostředí bez GTK
