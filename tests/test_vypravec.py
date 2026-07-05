"""Testy FÁZE 3 — vypravěč + A5 fit-check (M4), s mockem klienta i measurerem."""

import re

from honbicka.modely import Archetyp, Koncept, Profil
from honbicka.orchestrator import (
    MAX_ITERACI_KARTA,
    _kontext_karty,
    _potrebuje_30_variantu,
    _prompt_vypravec,
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
