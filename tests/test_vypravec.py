"""Testy FÁZE 3 — vypravěč + A5 fit-check (M4), s mockem klienta i measurerem.

Vypravěč vrací `KartaNavrh` (jen texty); strukturu (cíle voleb, číslo, typ)
vlastní graf a `sestav_kartu`. Párování voleb s hranami testuje
`test_vypravec_volby.py`."""

import re

from honbicka.modely import Archetyp, Karta, Koncept, Profil, TypUzlu, Volba
from honbicka.orchestrator import (
    MAX_ITERACI_KARTA,
    _kontext_karty,
    _prompt_vypravec,
    _synchronizuj_nazvy_uzlu,
    faze3_vypravec,
    napis_kartu,
)


class FakeKlient:
    def __init__(self, odpovedi=None, cyklus=None):
        self.odpovedi = list(odpovedi or [])
        self.cyklus = cyklus
        self.prompty: list[str] = []

    def generuj_json(self, role, uzivatel, schema, extra_system=None):
        self.prompty.append(uzivatel)
        if self.odpovedi:
            return self.odpovedi.pop(0)
        if self.cyklus is not None:
            return dict(self.cyklus)
        raise AssertionError("FakeKlient: došly odpovědi")


def measurer_dle_delky(html: str, sirka: float) -> float:
    text = re.sub(r"<[^>]+>", "", html)
    return len(text) / 45.0 * 5.0


def _navrh_dict(atmosfera, uvod="Krátký příběh bez voleb.", zaver="", volby=None):
    """KartaNavrh dict — default 2 volby (pokryjí každý uzel valid_mapa;
    přebytek se u uzlů s 1 hranou tiše ořízne)."""
    if volby is None:
        volby = [{"text": "Jdi dál po stopě", "vysledek": "Stopa vede k jezu"},
                 {"text": "Prohledej okolí", "vysledek": "V trávě leží klíč"}]
    return {"nazev": "X", "atmosfera": atmosfera, "uvod": uvod, "zaver": zaver,
            "volby": volby}


def _koncept():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody",
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                   falesne_teorie=1, pravdive_stopy=2, konce=2)


def test_uspech_na_prvni_pokus(valid_mapa, valid_zadani):
    klient = FakeKlient(odpovedi=[_navrh_dict("A" * 320)])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert all(f.verdikt for f in fits)
    assert log[-1]["pokus"] == 1
    # číslo a typ řídí graf, ne LLM
    assert karta.cislo == 8 and karta.typ == uzel.typ
    # navigace je z grafu: uzel 8 má jedinou hranu → 10
    assert "→ karta 10" in karta.zadni


def test_zkraceni_pres_llm(valid_mapa, valid_zadani):
    klient = FakeKlient(odpovedi=[_navrh_dict("A" * 4000), _navrh_dict("A" * 300)])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert all(f.verdikt for f in fits)
    assert len(klient.prompty) == 2
    assert "Zkrať" in klient.prompty[1]


def test_deterministicky_orez_atmosfery(valid_mapa, valid_zadani):
    # klient vždy vrací přetékající kartu → po 3 pokusech nastoupí ořez
    klient = FakeKlient(cyklus=_navrh_dict("A " * 1500))  # ~3000 znaků atmosféry
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert len(klient.prompty) == MAX_ITERACI_KARTA
    assert log[-1]["orez"] == "atmosfera"
    predni = next(f for f in fits if f.strana == "predni")
    assert predni.verdikt  # přední strana po ořezu sedne
    assert karta.atmosfera.endswith("…")


def test_zadni_30_je_deterministicky_filtr_side(valid_mapa, valid_zadani):
    # zadni_30 už nepíše LLM — vzniká filtrem SIDE voleb (spec §5).
    valid_mapa.uzel(4).profil = Profil.SIDE
    klient = FakeKlient(odpovedi=[_navrh_dict("A" * 320)])
    uzel2 = valid_mapa.uzel(2)  # hrany → [3, 4(SIDE)]
    karta, _, _ = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel2,
                              measurer=measurer_dle_delky)
    assert karta.ma_side_volbu
    assert karta.zadni_30 is not None
    assert "→ karta 3" in karta.zadni_30
    assert "→ karta 4" not in karta.zadni_30  # SIDE cíl v 30min variantě chybí
    assert "→ karta 4" in karta.zadni  # v 60min variantě je


def test_zadni_30_none_bez_side_voleb(valid_mapa, valid_zadani):
    klient = FakeKlient(odpovedi=[_navrh_dict("A" * 320)])
    karta, _, _ = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa,
                              valid_mapa.uzel(8), measurer=measurer_dle_delky)
    assert karta.zadni_30 is None


def test_faze3_projde_vsechny_karty(valid_mapa, valid_zadani):
    klient = FakeKlient(cyklus=_navrh_dict("A" * 300))
    karty, fit, log = faze3_vypravec(klient, valid_zadani, _koncept(), valid_mapa,
                                     measurer=measurer_dle_delky)
    assert len(karty) == len(valid_mapa.uzly)
    # čísla karet odpovídají uzlům (řízeno grafem)
    assert sorted(k.cislo for k in karty) == sorted(u.cislo for u in valid_mapa.uzly)


# ------- O3: koncept (mechanismus/rekvizita, před/po AHA) v promptu -------- #
def _koncept_bohaty():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody",
                   mechanismus_reseni="voda teče gravitací, ne kouzlem",
                   klicova_rekvizita="stříbrné sítko", falesne_teorie=1,
                   pravdive_stopy=2, konce=2)


def test_prompt_obsahuje_mechanismus_a_rekvizitu(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)  # obyčejný uzel, ne AHA
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept_bohaty(), uzel, kontext)
    assert "voda teče gravitací, ne kouzlem" in prompt
    assert "stříbrné sítko" in prompt
    assert "NIKDY neprozraď" in prompt


def test_prompt_rozlisuje_pred_a_po_aha(valid_mapa, valid_zadani):
    # uzel 3 (číslo < 8 = pozice AHA) → „před"; uzel 10 (> 8) → „po"
    pred = _kontext_karty(valid_mapa, valid_mapa.uzel(3))
    po = _kontext_karty(valid_mapa, valid_mapa.uzel(10))
    assert pred["pred_aha"] is True
    assert po["pred_aha"] is False
    prompt_pred = _prompt_vypravec(valid_zadani, _koncept_bohaty(), valid_mapa.uzel(3), pred)
    prompt_po = _prompt_vypravec(valid_zadani, _koncept_bohaty(), valid_mapa.uzel(10), po)
    assert "PŘED odhalením" in prompt_pred
    assert "PO odhalení" in prompt_po


def test_prompt_aha_karty_nema_pred_ani_po(valid_mapa, valid_zadani):
    # samotná AHA karta má svou vlastní instrukci (ne „před"/„po")
    uzel_aha = valid_mapa.uzel(valid_mapa.pozice_aha_uzel)
    kontext = _kontext_karty(valid_mapa, uzel_aha)
    prompt = _prompt_vypravec(valid_zadani, _koncept_bohaty(), uzel_aha, kontext)
    assert "ZDE padá AHA odhalení" in prompt
    assert "PŘED odhalením" not in prompt and "PO odhalení" not in prompt


# ------- SC3: synchronizace názvů uzlů ↔ karet ----------------------------- #
def _karta(cislo, nazev):
    return Karta(cislo=cislo, nazev=nazev, typ=TypUzlu.PRECHOD,
                 atmosfera="A" * 320, uvod="p")


def test_synchronizuj_nazvy_uzlu_prepise_genericky_nazev(valid_mapa):
    assert valid_mapa.uzel(8).nazev != "Kraj lesa"  # scaffolder dal generický název
    _synchronizuj_nazvy_uzlu(valid_mapa, [_karta(8, "Kraj lesa")])
    assert valid_mapa.uzel(8).nazev == "Kraj lesa"


def test_synchronizuj_nazvy_uzlu_rozlisi_duplicity(valid_mapa):
    karty = [_karta(u.cislo, "Stejný název") for u in valid_mapa.uzly]
    _synchronizuj_nazvy_uzlu(valid_mapa, karty)
    nazvy = [u.nazev for u in valid_mapa.uzly]
    assert len(nazvy) == len(set(nazvy))  # žádné dva uzly nemají stejné jméno
    # první karta v pořadí čísel si název ponechá beze změny
    prvni = min(valid_mapa.uzly, key=lambda u: u.cislo)
    assert prvni.nazev == "Stejný název"


def test_synchronizuj_nazvy_uzlu_ignoruje_kartu_bez_uzlu(valid_mapa):
    # karta na neexistující číslo (obranné chování, nemělo by nastat) nespadne
    _synchronizuj_nazvy_uzlu(valid_mapa, [_karta(99999, "Duch")])


def test_faze3_propise_nazvy_karet_do_mapy(valid_mapa, valid_zadani):
    """Integrace: po FÁZE 3 odpovídá mapa.uzel(n).nazev názvu vytištěné karty č. n
    (živě ověřený nesoulad — SC3)."""
    klient = FakeKlient(cyklus=_navrh_dict("A" * 300))
    karty, _, _ = faze3_vypravec(klient, valid_zadani, _koncept(), valid_mapa,
                                 measurer=measurer_dle_delky)
    karty_dle_cisla = {k.cislo: k.nazev for k in karty}
    for uzel in valid_mapa.uzly:
        ocekavany = karty_dle_cisla[uzel.cislo]
        assert uzel.nazev == ocekavany or uzel.nazev == f"{ocekavany} ({uzel.cislo})"


# ------- O4: slovník žánru (forbidden_terms) -------------------------------- #
def _koncept_zakazana(slova):
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody",
                   mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                   falesne_teorie=1, pravdive_stopy=2, konce=2, slovnik_zakazana=slova)


def test_najdi_zakazane_slovo_najde_substring():
    from honbicka.orchestrator import _najdi_zakazane_slovo
    karta = Karta(cislo=1, nazev="X", typ=TypUzlu.PRECHOD, atmosfera="A" * 300,
                  uvod="Tady někdo chtěl zabít draka.")
    assert _najdi_zakazane_slovo(karta, ["zabít"]) == "zabít"


def test_najdi_zakazane_slovo_hleda_i_ve_volbach():
    from honbicka.orchestrator import _najdi_zakazane_slovo
    karta = Karta(cislo=1, nazev="X", typ=TypUzlu.PRECHOD, atmosfera="A" * 300,
                  uvod="Klidný úvod.",
                  volby=[Volba(text="Vytas meč", vysledek="Chceš draka ZABÍT", cil=2)])
    assert _najdi_zakazane_slovo(karta, ["zabít"]) == "zabít"


def test_najdi_zakazane_slovo_case_insensitive_a_prazdny_seznam():
    from honbicka.orchestrator import _najdi_zakazane_slovo
    karta = Karta(cislo=1, nazev="X", typ=TypUzlu.PRECHOD, atmosfera="A" * 300,
                  uvod="ZABÍT draka.")
    assert _najdi_zakazane_slovo(karta, ["zabít"]) == "zabít"
    assert _najdi_zakazane_slovo(karta, []) is None
    assert _najdi_zakazane_slovo(karta, ["krev"]) is None


def test_prompt_obsahuje_zakazana_slova(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept_zakazana(["zabít", "krev"]), uzel,
                              kontext)
    assert "zabít" in prompt and "krev" in prompt
    assert "ZAKÁZANÁ SLOVA" in prompt


def test_prompt_bez_zakazanych_slov_nema_sekci(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept(), uzel, kontext)
    assert "ZAKÁZANÁ SLOVA" not in prompt


def test_prompt_oprava_slovnik_zminuje_konkretni_slovo(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept_zakazana(["zabít"]), uzel, kontext,
                              oprava_slovnik="zabít")
    assert "zakázané slovo „zabít“" in prompt


def test_napis_kartu_opravi_zakazane_slovo_pres_retry(valid_mapa, valid_zadani):
    spatna = _navrh_dict("A" * 320, uvod="Tady chtěl někdo draka zabít.")
    dobra = _navrh_dict("A" * 320)
    klient = FakeKlient(odpovedi=[spatna, dobra])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept_zakazana(["zabít"]),
                                   valid_mapa, uzel, measurer=measurer_dle_delky)
    assert "zabít" not in karta.predni.lower()
    assert any(e.get("zakazane_slovo") == "zabít" for e in log)
    assert len(klient.prompty) == 2
    assert "zabít" in klient.prompty[1]  # opravný prompt cituje konkrétní slovo


def test_napis_kartu_zaznamena_neopravitelne_zakazane_slovo(valid_mapa, valid_zadani):
    # model 3× vrátí totéž zakázané slovo → Python to nepřepisuje, jen zaznamená
    spatna = _navrh_dict("A" * 320, uvod="Tady chtěl někdo draka zabít.")
    klient = FakeKlient(cyklus=spatna)
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept_zakazana(["zabít"]),
                                   valid_mapa, uzel, measurer=measurer_dle_delky)
    assert any(e.get("slovnik_neopravitelne") == "zabít" for e in log)
