"""Testy sazby (M5): imposice karet, kalibrace, počet stran, herní list, průvodce.
Bez GTK — testuje se HTML/struktura, ne reálné PDF."""

import pytest

from honbicka.modely import Archetyp, Karta, Koncept, TypUzlu, VekPasmo, Zadani
from honbicka.sazba.herni_list import postav_html_herni_list
from honbicka.sazba.karty_pdf import (
    pocet_stran,
    postav_html_karet,
    spocti_archy,
    zkontroluj_pocet_stran,
)
from honbicka.sazba.pruvodce import CHECKLIST, FEEDBACK_OTAZKY, postav_html_pruvodce


def _karty(n, s_variantou_30=False):
    out = []
    for i in range(1, n + 1):
        out.append(Karta(
            cislo=i, nazev=f"Karta {i}", typ=TypUzlu.POSTAVA,
            atmosfera="Atmosféra " * 5, predni=f"Příběh {i}.", zadni=f"Výsledek {i}.",
            zadni_30=(f"Výsledek {i} bez SIDE." if s_variantou_30 else None),
        ))
    return out


@pytest.mark.parametrize("n,strany", [(1, 4), (2, 4), (3, 6), (4, 6), (5, 8), (11, 14)])
def test_pocet_stran_formule(n, strany):
    assert pocet_stran(n) == strany  # 2 kalibrace + 2×⌈n/2⌉


def test_html_ma_spravny_pocet_archu():
    karty = _karty(5)
    html = postav_html_karet(karty, nadpis="Test")
    assert spocti_archy(html) == pocet_stran(5)
    assert zkontroluj_pocet_stran(html, 5)


def test_kalibracni_arch_je_prvni():
    html = postav_html_karet(_karty(2), nadpis="Test")
    assert "KALIBRACE — PŘEDNÍ" in html
    assert "KALIBRACE — ZADNÍ" in html
    # kalibrace před první kartou
    assert html.index("KALIBRACE") < html.index("Karta 1")


def test_kalibracni_znacka_je_mimo_stred_a_asymetricka():
    # SZ1: symetrický čtverec uprostřed neodhalí zrcadlené otočení; značka
    # musí být mimo osy souměrnosti slotu (148.5×210 mm) a mít asymetrický tvar.
    html = postav_html_karet(_karty(2), nadpis="Test")
    assert "left:15mm;top:15mm" in html  # mimo střed (bylo by ~74mm/105mm)
    # trojúhelník (asymetrický tvar) přes rozdílné CSS border strany
    assert "border-left:15mm solid #000" in html
    assert "border-top:10mm solid transparent" in html


def test_kalibrace_zminuje_obe_varianty_otoceni():
    # SZ1: správný duplex režim závisí na ovladači tiskárny — kalibrace musí
    # nabídnout obě varianty, ne jen předpokládat jednu.
    html = postav_html_karet(_karty(2), nadpis="Test").lower()
    assert "delší straně" in html
    assert "kratší straně" in html
    assert "směr" in html and "horní roh" in html


def test_css_pasti_weasyprint():
    html = postav_html_karet(_karty(2), nadpis="Test")
    assert "margin: 0" in html            # body margin 0
    assert "position: absolute" in html   # karty absolutně, ne flex/grid
    assert "display: flex" not in html
    assert "display: grid" not in html
    assert "DejaVu Sans" in html          # čeština


def test_rez_a_dve_karty_na_arch():
    html = postav_html_karet(_karty(2), nadpis="Test")
    # každý datový arch má levý i pravý slot + řez
    assert "slot-left" in html and "slot-right" in html
    assert "class='rez'" in html


def test_30min_pouziva_zadni_30():
    karty = _karty(2, s_variantou_30=True)
    html60 = postav_html_karet(karty, nadpis="60", zadni_strana="zadni")
    html30 = postav_html_karet(karty, nadpis="30", zadni_strana="zadni_30")
    assert "Výsledek 1." in html60 and "bez SIDE" not in html60.split("Výsledek 1.")[0]
    assert "bez SIDE" in html30


# ------- herní list -------------------------------------------------------- #
def test_herni_list_inventar_dle_profilu():
    h30 = postav_html_herni_list(tema="Kapka", prah=100, profil_min=30,
                                 format_hracu="dvojice", pocet_komponent=2)
    h60 = postav_html_herni_list(tema="Kapka", prah=100, profil_min=60,
                                 format_hracu="dvojice", pocet_komponent=3)
    assert h30.count("class='slot-inv'") == 3
    assert h60.count("class='slot-inv'") == 5


def test_herni_list_teorie_dle_formatu():
    tym = postav_html_herni_list(tema="X", prah=90, profil_min=60,
                                 format_hracu="tymy_4x4", pocet_komponent=3)
    assert "SÁZKA TÝMU" in tym
    volny = postav_html_herni_list(tema="X", prah=90, profil_min=60,
                                   format_hracu="volny_format", pocet_komponent=3,
                                   je_volny_format=True)
    assert "PRVNÍ návštěvě" in volny  # dodatek 3.4-3 na herním listu


def test_herni_list_pocitadlo_po_petkach():
    h = postav_html_herni_list(tema="X", prah=100, profil_min=30,
                               format_hracu="jednotlivci", pocet_komponent=2)
    assert h.count("<span></span>") == 100  # 20 skupin po 5


# ------- průvodce ---------------------------------------------------------- #
def _pruvodce_html():
    koncept = Koncept(archetyp=Archetyp.A1, tema="Kapka vody",
                      mechanismus_reseni="průnik tří stop", klicova_rekvizita="sítko",
                      falesne_teorie=1, pravdive_stopy=3, konce=2)
    zadani = Zadani(vek=VekPasmo.V06_09, format_hracu="tymy_4x4")
    from tests.conftest import build_valid_mapa
    mapa = build_valid_mapa()
    karty = _karty(3)
    return postav_html_pruvodce(koncept=koncept, zadani=zadani, mapa=mapa,
                                karty=karty, prah=100)


def test_pruvodce_ma_vsechny_sekce():
    html = _pruvodce_html()
    for nadpis in ("Spoiler přehled", "Správná odpověď", "Rozmístění uzlů",
                   "Stavěcí checklist", "Brífink", "EPILOG", "Kdy zasáhnout",
                   "redakční posudek", "Feedback", "Tisková instrukce", "Příloha"):
        assert nadpis in html, nadpis


def test_pruvodce_feedback_5_otazek():
    html = _pruvodce_html()
    assert len(FEEDBACK_OTAZKY) == 5
    for o in FEEDBACK_OTAZKY:
        assert o in html


def test_pruvodce_checklist_casy():
    html = _pruvodce_html()
    for _, cas in CHECKLIST:
        assert cas in html
    assert "duplex" in html.lower()  # tisková instrukce


def test_pruvodce_priloha_obsahuje_karty():
    html = _pruvodce_html()
    assert "Karta 1" in html and "Karta 3" in html
