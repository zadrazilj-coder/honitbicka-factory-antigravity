"""Testy O1/T1: volby v textu karty MUSÍ odpovídat skutečným hranám grafu.

Živý běh „čtyři světla" ukázal, že vypravěč si čísla voleb umí vymyslet
(karta odkazovala „→8" sama na sebe místo skutečné hrany 8→11). Tyto testy
pokrývají extrakci čísel, ověření proti grafu, opravnou smyčku a
deterministický fallback."""

from __future__ import annotations

import re

from honbicka.modely import Archetyp, Karta, Koncept, Profil, TypUzlu
from honbicka.orchestrator import (
    MAX_ITERACI_KARTA,
    _extrahuj_cisla_voleb,
    _nouzova_karta,
    _ocekavana_cisla_voleb,
    _oprav_volby_deterministicky,
    _prompt_vypravec,
    _volby_v_karte_platne,
    napis_kartu,
)


def measurer_dle_delky(html: str, sirka: float) -> float:
    text = re.sub(r"<[^>]+>", "", html)
    return len(text) / 45.0 * 5.0


def _koncept():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody", mechanismus_reseni="průnik stop",
                   falesne_teorie=1, pravdive_stopy=2, konce=2)


def _karta(cislo, predni, zadni, zadni_30=None):
    return Karta(cislo=cislo, nazev="X", typ=TypUzlu.POSTAVA, atmosfera="A" * 320,
                 predni=predni, zadni=zadni, zadni_30=zadni_30)


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


def _karta_dict(predni, zadni, atmosfera="A" * 320):
    return {"cislo": 1, "nazev": "X", "typ": "postava",
            "atmosfera": atmosfera, "predni": predni, "zadni": zadni}


# ------- extrakce a ověření ------------------------------------------------ #
def test_extrahuj_cisla_voleb():
    assert _extrahuj_cisla_voleb("A) jdi →2  B) zůstaň →3") == {2, 3}
    assert _extrahuj_cisla_voleb("bez šipek") == set()
    assert _extrahuj_cisla_voleb("→10 a taky →10 znovu") == {10}


def test_ocekavana_cisla_voleb_core_vylouci_side(valid_mapa):
    valid_mapa.uzel(4).profil = Profil.SIDE
    uzel2 = valid_mapa.uzel(2)  # hrany → [3, 4]
    assert _ocekavana_cisla_voleb(valid_mapa, uzel2) == {3, 4}
    assert _ocekavana_cisla_voleb(valid_mapa, uzel2, jen_core=True) == {3}


def test_volby_platne_pro_spravna_cisla(valid_mapa):
    uzel8 = valid_mapa.uzel(8)  # jediná hrana → 10
    karta = _karta(8, "A) →10", "Výsledek →10")
    assert _volby_v_karte_platne(karta, uzel8, valid_mapa)


def test_volby_neplatne_kdyz_odkazuje_na_sebe(valid_mapa):
    # přesně živě pozorovaný bug: karta 8 odkazovala „→8" místo skutečné hrany →10.
    uzel8 = valid_mapa.uzel(8)
    karta = _karta(8, "A) →8  B) →10", "Výsledek →10")
    assert not _volby_v_karte_platne(karta, uzel8, valid_mapa)


def test_volby_neplatne_kdyz_chybi_sipka(valid_mapa):
    uzel8 = valid_mapa.uzel(8)
    karta = _karta(8, "Text bez šipky vůbec.", "Výsledek bez šipky.")
    assert not _volby_v_karte_platne(karta, uzel8, valid_mapa)


def test_cilova_karta_bez_hran_vzdy_platna(valid_mapa):
    cil = next(u for u in valid_mapa.uzly if u.typ == TypUzlu.CIL)
    karta = _karta(cil.cislo, "Konec příběhu.", "Hra skončila.")
    assert _volby_v_karte_platne(karta, cil, valid_mapa)


def test_zadni_30_se_kontroluje_proti_core_mnozine(valid_mapa):
    valid_mapa.uzel(4).profil = Profil.SIDE
    uzel2 = valid_mapa.uzel(2)  # hrany → [3, 4(SIDE)]
    # zadni_30 smí odkazovat jen na 3 (core), ne na 4 (SIDE)
    karta_ok = _karta(2, "A) →3  B) →4", "Výsledek →3 nebo →4", zadni_30="Jen →3")
    assert _volby_v_karte_platne(karta_ok, uzel2, valid_mapa)
    karta_spatne = _karta(2, "A) →3  B) →4", "Výsledek →3 nebo →4", zadni_30="Chybně →4")
    assert not _volby_v_karte_platne(karta_spatne, uzel2, valid_mapa)


# ------- deterministická oprava -------------------------------------------- #
def test_oprav_volby_deterministicky_jediny_cil(valid_mapa):
    uzel8 = valid_mapa.uzel(8)  # jediná hrana → 10
    karta = _karta(8, "A) →8  B) →99", "Výsledek →8")
    opravena = _oprav_volby_deterministicky(karta, uzel8, valid_mapa)
    assert _volby_v_karte_platne(opravena, uzel8, valid_mapa)
    assert "→10" in opravena.predni and "→10" in opravena.zadni


def test_oprav_volby_deterministicky_vice_cilu_beze_zmeny(valid_mapa):
    uzel7 = valid_mapa.uzel(7)  # dvě hrany → {8, 9} — nejednoznačné
    karta = _karta(7, "A) →99  B) →98", "Výsledek →99")
    opravena = _oprav_volby_deterministicky(karta, uzel7, valid_mapa)
    # nejednoznačné (2 platné cíle) → beze změny, stále neplatné
    assert opravena.predni == "A) →99  B) →98"
    assert not _volby_v_karte_platne(opravena, uzel7, valid_mapa)


# ------- prompt: tvrdý požadavek + opravný text ---------------------------- #
def test_prompt_obsahuje_tvrda_cisla(valid_mapa):
    uzel8 = valid_mapa.uzel(8)
    kontext = {"sousedi": [{"cislo": 10, "nazev": "X", "podminka": None, "side": False}],
               "je_aha": False, "klicove_svedectvi": False, "pred_aha": True}
    from honbicka.modely import Obtiznost, VekPasmo, Zadani
    zadani = Zadani(vek=VekPasmo.V09_12, obtiznost=Obtiznost.LEHKA)
    prompt = _prompt_vypravec(zadani, _koncept(), uzel8, kontext, False, None)
    assert "[10]" in prompt and "KRITICKÉ" in prompt
    assert str(uzel8.cislo) in prompt  # zmíněno jako zakázané číslo


def test_prompt_oprava_voleb_pridava_text(valid_mapa):
    uzel8 = valid_mapa.uzel(8)
    kontext = {"sousedi": [{"cislo": 10, "nazev": "X", "podminka": None, "side": False}],
               "je_aha": False, "klicove_svedectvi": False, "pred_aha": True}
    from honbicka.modely import Obtiznost, VekPasmo, Zadani
    zadani = Zadani(vek=VekPasmo.V09_12, obtiznost=Obtiznost.LEHKA)
    prompt = _prompt_vypravec(zadani, _koncept(), uzel8, kontext, False, None,
                              oprava_voleb=True)
    assert "ŠPATNÁ čísla" in prompt


# ------- end-to-end napis_kartu --------------------------------------------- #
def test_napis_kartu_opravi_volby_pres_retry(valid_mapa, valid_zadani):
    # 1. pokus: špatné číslo (sebe-odkaz); 2. pokus: správné → uspěje
    klient = FakeKlient(odpovedi=[
        _karta_dict("A) →8  B) →10", "Výsledek →8"),
        _karta_dict("A) →10  B) →10", "Výsledek →10"),
    ])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert _volby_v_karte_platne(karta, uzel, valid_mapa)
    assert any(e.get("volby_chyba") for e in log)
    assert len(klient.prompty) == 2
    assert "ŠPATNÁ čísla" in klient.prompty[1]


def test_napis_kartu_deterministicka_oprava_po_vycerpani_pokusu(valid_mapa, valid_zadani):
    # model 3× vrátí špatné číslo → poslední záchrana: deterministická oprava
    # (uzel 8 má jediný platný cíl → 10, oprava je jednoznačná a bezpečná)
    klient = FakeKlient(cyklus=_karta_dict("A) →8  B) →8", "Výsledek →8"))
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert len(klient.prompty) == MAX_ITERACI_KARTA
    assert _volby_v_karte_platne(karta, uzel, valid_mapa)
    assert any(e.get("volby_opraveny_deterministicky") for e in log)


def test_napis_kartu_neopravitelne_se_zaloguje(valid_mapa, valid_zadani):
    # uzel 7 má DVĚ hrany (8 i 9) — špatné číslo nelze jednoznačně opravit
    klient = FakeKlient(cyklus=_karta_dict("A) →99  B) →98", "Výsledek →99"))
    uzel = valid_mapa.uzel(7)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert karta is not None  # hra se nezastaví
    assert any(e.get("volby_neopravitelne") for e in log)


# ------- O6: nouzová karta má platnou navigaci ----------------------------- #
def test_nouzova_karta_ma_platne_volby_jedna_hrana(valid_mapa):
    # uzel 8 má jedinou hranu → 10
    uzel = valid_mapa.uzel(8)
    karta = _nouzova_karta(uzel, _koncept(), valid_mapa)
    assert _volby_v_karte_platne(karta, uzel, valid_mapa)
    assert _extrahuj_cisla_voleb(karta.predni) == {10}
    assert _extrahuj_cisla_voleb(karta.zadni) == {10}


def test_nouzova_karta_ma_platne_volby_vice_hran(valid_mapa):
    # uzel 7 má dvě hrany → {8, 9}
    uzel = valid_mapa.uzel(7)
    karta = _nouzova_karta(uzel, _koncept(), valid_mapa)
    assert _volby_v_karte_platne(karta, uzel, valid_mapa)
    assert _extrahuj_cisla_voleb(karta.predni) == {8, 9}


def test_nouzova_karta_cilova_karta_bez_voleb(valid_mapa):
    cil = next(u for u in valid_mapa.uzly if u.typ == TypUzlu.CIL)
    karta = _nouzova_karta(cil, _koncept(), valid_mapa)
    assert _volby_v_karte_platne(karta, cil, valid_mapa)  # bez hran = vždy platné
    assert _extrahuj_cisla_voleb(karta.predni) == set()  # žádné (falešné) →N


def test_nouzova_karta_ma_zadni_30_pro_core_rozcestnik(valid_mapa):
    # uzel 2 → [3, 4]; uděláme 4 jako SIDE, aby uzel 2 potřeboval zadni_30
    valid_mapa.uzel(4).profil = Profil.SIDE
    uzel = valid_mapa.uzel(2)
    karta = _nouzova_karta(uzel, _koncept(), valid_mapa)
    assert karta.zadni_30 is not None
    assert _extrahuj_cisla_voleb(karta.zadni_30) == {3}  # jen CORE cíl
    assert _volby_v_karte_platne(karta, uzel, valid_mapa)


def test_napis_kartu_nouzova_karta_po_vycerpani_schema_pokusu(valid_mapa, valid_zadani):
    # model 3× vrátí nepoužitelný obsah (chybí povinná pole) → nouzová karta
    # MUSÍ mít platnou navigaci, ne rozbité "Cesta pokračuje dál." bez čísel.
    klient = FakeKlient(cyklus={"nesmysl": True})
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert any(e.get("nouzova_karta") for e in log)
    assert _volby_v_karte_platne(karta, uzel, valid_mapa)
