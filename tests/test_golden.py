"""Golden game (spec §10): známá hra projde deterministicky celou sazbou +
validací bez LLM → stabilní počet stran, fit-check zelený, správné pořadí
zadních stran, kalibrační arch."""

import re

from honbicka.modely import Archetyp, Karta, Koncept, Obtiznost, VekPasmo, Zadani
from honbicka.sazba.karty_pdf import pocet_stran, postav_html_karet, spocti_archy
from honbicka.validatory.agregace import validuj_par_30_60
from honbicka.validatory.sazba import fit_check_karty
from tests.conftest import build_valid_mapa_60


def _measurer(html, sirka):
    return len(re.sub(r"<[^>]+>", "", html)) / 45.0 * 5.0


def _golden_karty(mapa):
    """Deterministické karty pro každý uzel (krátké → sednou na A5)."""
    return [
        Karta(cislo=u.cislo, nazev=f"Uzel {u.cislo}", typ=u.typ,
              atmosfera="Klidná atmosféra u potoka, kde se cosi skrývá.",
              predni=f"Příběh uzlu {u.cislo}. Vyber cestu.", zadni=f"Výsledek {u.cislo}.")
        for u in sorted(mapa.uzly, key=lambda u: u.cislo)
    ]


def test_golden_validace_prochazi():
    mapa = build_valid_mapa_60()
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", obtiznost=Obtiznost.LEHKA)
    koncept = Koncept(archetyp=Archetyp.A1, tema="Kapka", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=2, pravdive_stopy=3, konce=2)
    v, _ = validuj_par_30_60(mapa, zadani, koncept)
    assert v.ok, v.chyby


def test_golden_fit_check_zeleny():
    mapa = build_valid_mapa_60()
    karty = _golden_karty(mapa)
    for k in karty:
        for f in fit_check_karty(k, measurer=_measurer):
            assert f.verdikt, (k.cislo, f.strana, f.vyska_mm, f.limit_mm)


def test_golden_pocet_stran_stabilni():
    mapa = build_valid_mapa_60()
    karty = _golden_karty(mapa)
    core_cisla = {u.cislo for u in mapa.core_uzly}
    core_karty = [k for k in karty if k.cislo in core_cisla]

    html60 = postav_html_karet(karty, nadpis="60")
    html30 = postav_html_karet(core_karty, nadpis="30", zadni_strana="zadni_30")
    assert spocti_archy(html60) == pocet_stran(20) == 22  # 2 + 2×10
    assert spocti_archy(html30) == pocet_stran(11) == 14  # 2 + 2×6


def test_golden_arch_ma_presne_dva_sloty():
    mapa = build_valid_mapa_60()
    html = postav_html_karet(_golden_karty(mapa), nadpis="60")
    archy = html.split("class='arch'")[1:]  # každý fragment = jeden arch
    for arch in archy:
        assert arch.count("class='slot") == 2  # přesně 2 karty/stranu


def test_golden_zadni_strany_neprohozene():
    # duplex „otáčet po delší straně" → zadní strany ve STEJNÉM pořadí (levá=levá)
    mapa = build_valid_mapa_60()
    html = postav_html_karet(_golden_karty(mapa), nadpis="60")
    archy = html.split("class='arch'")[1:]
    front, back = archy[2], archy[3]  # první dvojice karet (archy[0,1] = kalibrace)
    # #1 vlevo, #2 vpravo v přední i zadní straně (nesmí se prohodit)
    assert front.index("#1") < front.index("#2")
    assert back.index("#1") < back.index("#2")


def test_golden_kalibracni_arch_pritomen():
    html = postav_html_karet(_golden_karty(build_valid_mapa_60()), nadpis="60")
    assert "KALIBRACE — PŘEDNÍ" in html and "KALIBRACE — ZADNÍ" in html
