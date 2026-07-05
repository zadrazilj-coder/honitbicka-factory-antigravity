"""Testy FÁZE 3 — vypravěč + A5 fit-check (M4), s mockem klienta i measurerem."""

import re

from honbicka.modely import Archetyp, Karta, Koncept, Profil, TypUzlu
from honbicka.orchestrator import (
    MAX_ITERACI_KARTA,
    _kontext_karty,
    _potrebuje_30_variantu,
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


def _karta_dict(atmosfera, predni="Krátký příběh a volby. →10", zadni="Výsledek. →10",
                zadni_30=None):
    # →10 odpovídá jediné hraně uzlu 8 ve valid_mapa (viz conftest) — testy níže
    # ověřují schéma/fit-check/ořez, ne kontrolu voleb↔grafu (O1, viz test_vypravec_volby.py).
    d = {"cislo": 1, "nazev": "X", "typ": "postava",
         "atmosfera": atmosfera, "predni": predni, "zadni": zadni}
    if zadni_30 is not None:
        d["zadni_30"] = zadni_30
    return d


def _koncept():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                   falesne_teorie=1, pravdive_stopy=2, konce=2)


def test_uspech_na_prvni_pokus(valid_mapa, valid_zadani):
    klient = FakeKlient(odpovedi=[_karta_dict("A" * 320)])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert all(f.verdikt for f in fits)
    assert log[-1]["pokus"] == 1
    # číslo a typ řídí graf, ne LLM
    assert karta.cislo == 8 and karta.typ == uzel.typ


def test_zkraceni_pres_llm(valid_mapa, valid_zadani):
    klient = FakeKlient(odpovedi=[_karta_dict("A" * 4000), _karta_dict("A" * 300)])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert all(f.verdikt for f in fits)
    assert len(klient.prompty) == 2
    assert "Zkrať" in klient.prompty[1]


def test_deterministicky_orez_atmosfery(valid_mapa, valid_zadani):
    # klient vždy vrací přetékající kartu → po 3 pokusech nastoupí ořez
    klient = FakeKlient(cyklus=_karta_dict("A " * 1500))  # ~3000 znaků atmosféry
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert len(klient.prompty) == MAX_ITERACI_KARTA
    assert log[-1]["orez"] == "atmosfera"
    predni = next(f for f in fits if f.strana == "predni")
    assert predni.verdikt  # přední strana po ořezu sedne
    assert karta.atmosfera.endswith("…")


def test_potrebuje_30_variantu(valid_mapa):
    # uzel 2 (CORE rozcestník) → uděláme uzel 4 jako SIDE
    valid_mapa.uzel(4).profil = Profil.SIDE
    assert _potrebuje_30_variantu(valid_mapa, valid_mapa.uzel(2)) is True
    assert _potrebuje_30_variantu(valid_mapa, valid_mapa.uzel(8)) is False


def test_zadni_30_vynulovano_kdyz_neni_side(valid_mapa, valid_zadani):
    # uzel 8 nemá SIDE souseda → zadni_30 se zahodí i kdyby ji LLM dodal
    klient = FakeKlient(odpovedi=[_karta_dict("A" * 320, zadni_30="navíc")])
    karta, _, _ = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, valid_mapa.uzel(8),
                              measurer=measurer_dle_delky)
    assert karta.zadni_30 is None


def test_faze3_projde_vsechny_karty(valid_mapa, valid_zadani):
    klient = FakeKlient(cyklus=_karta_dict("A" * 300))
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
    prompt = _prompt_vypravec(valid_zadani, _koncept_bohaty(), uzel, kontext, False, None)
    assert "voda teče gravitací, ne kouzlem" in prompt
    assert "stříbrné sítko" in prompt
    assert "NIKDY neprozraď" in prompt


def test_prompt_rozlisuje_pred_a_po_aha(valid_mapa, valid_zadani):
    # uzel 3 (číslo < 8 = pozice AHA) → „před"; uzel 10 (> 8) → „po"
    pred = _kontext_karty(valid_mapa, valid_mapa.uzel(3))
    po = _kontext_karty(valid_mapa, valid_mapa.uzel(10))
    assert pred["pred_aha"] is True
    assert po["pred_aha"] is False
    prompt_pred = _prompt_vypravec(valid_zadani, _koncept_bohaty(), valid_mapa.uzel(3),
                                   pred, False, None)
    prompt_po = _prompt_vypravec(valid_zadani, _koncept_bohaty(), valid_mapa.uzel(10),
                                 po, False, None)
    assert "PŘED odhalením" in prompt_pred
    assert "PO odhalení" in prompt_po


def test_prompt_aha_karty_nema_pred_ani_po(valid_mapa, valid_zadani):
    # samotná AHA karta má svou vlastní instrukci (ne „před"/„po")
    uzel_aha = valid_mapa.uzel(valid_mapa.pozice_aha_uzel)
    kontext = _kontext_karty(valid_mapa, uzel_aha)
    prompt = _prompt_vypravec(valid_zadani, _koncept_bohaty(), uzel_aha, kontext, False, None)
    assert "ZDE padá AHA odhalení" in prompt
    assert "PŘED odhalením" not in prompt and "PO odhalení" not in prompt


# ------- SC3: synchronizace názvů uzlů ↔ karet ----------------------------- #
def _karta(cislo, nazev):
    return Karta(cislo=cislo, nazev=nazev, typ=TypUzlu.PRECHOD,
                 atmosfera="A" * 320, predni="p", zadni="z")


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
    klient = FakeKlient(cyklus=_karta_dict("A" * 300))
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
                 predni="Tady někdo chtěl zabít draka.", zadni="Konec.")
    assert _najdi_zakazane_slovo(karta, ["zabít"]) == "zabít"


def test_najdi_zakazane_slovo_case_insensitive_a_prazdny_seznam():
    from honbicka.orchestrator import _najdi_zakazane_slovo
    karta = Karta(cislo=1, nazev="X", typ=TypUzlu.PRECHOD, atmosfera="A" * 300,
                 predni="ZABÍT draka.", zadni="Konec.")
    assert _najdi_zakazane_slovo(karta, ["zabít"]) == "zabít"
    assert _najdi_zakazane_slovo(karta, []) is None
    assert _najdi_zakazane_slovo(karta, ["krev"]) is None


def test_prompt_obsahuje_zakazana_slova(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept_zakazana(["zabít", "krev"]), uzel,
                              kontext, False, None)
    assert "zabít" in prompt and "krev" in prompt
    assert "ZAKÁZANÁ SLOVA" in prompt


def test_prompt_bez_zakazanych_slov_nema_sekci(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept(), uzel, kontext, False, None)
    assert "ZAKÁZANÁ SLOVA" not in prompt


def test_prompt_oprava_slovnik_zminuje_konkretni_slovo(valid_mapa, valid_zadani):
    uzel = valid_mapa.uzel(3)
    kontext = _kontext_karty(valid_mapa, uzel)
    prompt = _prompt_vypravec(valid_zadani, _koncept_zakazana(["zabít"]), uzel, kontext,
                              False, None, oprava_slovnik="zabít")
    assert "zakázané slovo „zabít“" in prompt


def test_napis_kartu_opravi_zakazane_slovo_pres_retry(valid_mapa, valid_zadani):
    spatna = _karta_dict("A" * 320, predni="Tady chtěl někdo draka zabít. →10")
    dobra = _karta_dict("A" * 320)
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
    spatna = _karta_dict("A" * 320, predni="Tady chtěl někdo draka zabít. →10")
    klient = FakeKlient(cyklus=spatna)
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept_zakazana(["zabít"]),
                                   valid_mapa, uzel, measurer=measurer_dle_delky)
    assert any(e.get("slovnik_neopravitelne") == "zabít" for e in log)
