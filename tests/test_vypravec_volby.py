"""Testy párování voleb s hranami grafu (`sestav_kartu`) a rendereru stran.

Nahrazuje dřívější O1 regex-kontrolu „→N v próze ↔ hrany": živá data ukázala,
že regex měl díru („→ slepa 10" neviděl — viz docs/analyza_dsl_a_architektury.md
§3). Volby jsou teď DATA: cíl/podmínku/side doplňuje Python z hran, navigaci
(„→ karta N") skládá renderer — nesoulad s grafem je nemožný z konstrukce."""

from __future__ import annotations

import re

from honbicka.modely import (
    Archetyp,
    Karta,
    KartaNavrh,
    Koncept,
    Profil,
    TypUzlu,
    Volba,
    VolbaNavrh,
)
from honbicka.orchestrator import (
    MAX_ITERACI_KARTA,
    _nouzova_karta,
    _prompt_vypravec,
    napis_kartu,
    sestav_kartu,
)


def measurer_dle_delky(html: str, sirka: float) -> float:
    text = re.sub(r"<[^>]+>", "", html)
    return len(text) / 45.0 * 5.0


def _koncept():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody",
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                   falesne_teorie=1, pravdive_stopy=2, konce=2)


def _navrh(pocet_voleb, atmosfera="A" * 320):
    return KartaNavrh(nazev="X", atmosfera=atmosfera, uvod="Úvodní příběh.",
                      volby=[VolbaNavrh(text=f"Akce {i}", vysledek=f"Výsledek {i}")
                             for i in range(1, pocet_voleb + 1)])


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


def _navrh_dict(pocet_voleb, atmosfera="A" * 320):
    return {"nazev": "X", "atmosfera": atmosfera, "uvod": "Úvodní příběh.", "zaver": "",
            "volby": [{"text": f"Akce {i}", "vysledek": f"Výsledek {i}"}
                      for i in range(1, pocet_voleb + 1)]}


# ------- sestav_kartu: párování voleb ↔ hrany ------------------------------ #
def test_sestav_kartu_paruje_cile_z_grafu(valid_mapa):
    uzel7 = valid_mapa.uzel(7)  # hrany → [8, 9]
    karta = sestav_kartu(_navrh(2), uzel7, valid_mapa)
    assert karta is not None
    assert [v.cil for v in karta.volby] == [8, 9]  # pořadí hran, ne LLM
    assert karta.cislo == 7 and karta.typ == uzel7.typ


def test_sestav_kartu_prebytecne_volby_orizne(valid_mapa):
    uzel8 = valid_mapa.uzel(8)  # jediná hrana → 10
    karta = sestav_kartu(_navrh(3), uzel8, valid_mapa)
    assert karta is not None
    assert len(karta.volby) == 2 and karta.volby[0].cil == 10 and karta.volby[1].cil == 10


def test_sestav_kartu_malo_voleb_vraci_none(valid_mapa):
    uzel7 = valid_mapa.uzel(7)  # 2 hrany
    assert sestav_kartu(_navrh(1), uzel7, valid_mapa) is None


def test_sestav_kartu_doplnit_pridava_genericke_volby(valid_mapa):
    uzel7 = valid_mapa.uzel(7)  # 2 hrany
    karta = sestav_kartu(_navrh(1), uzel7, valid_mapa, doplnit=True)
    assert karta is not None
    assert [v.cil for v in karta.volby] == [8, 9]
    assert karta.volby[0].text == "Akce 1"          # LLM text zachován
    assert karta.volby[1].text == "Pokračuj dál"    # chybějící doplněn genericky


def test_sestav_kartu_prenasi_podminku_a_side(valid_mapa):
    valid_mapa.uzel(4).profil = Profil.SIDE
    uzel2 = valid_mapa.uzel(2)  # hrany → [3, 4(SIDE)]
    uzel2.hrany[0].podminka = "LUCERNA"
    karta = sestav_kartu(_navrh(2), uzel2, valid_mapa)
    assert karta.volby[0].podminka == "LUCERNA" and not karta.volby[0].side
    assert karta.volby[1].side


def test_sestav_kartu_cilova_karta_bez_hran(valid_mapa):
    cil = next(u for u in valid_mapa.uzly if u.typ == TypUzlu.CIL)
    karta = sestav_kartu(_navrh(0), cil, valid_mapa)
    assert karta is not None and karta.volby == []
    # volby navíc u cílové karty se tiše oříznou (0 hran)
    karta2 = sestav_kartu(_navrh(2), cil, valid_mapa)
    assert karta2 is not None and karta2.volby == []


# ------- renderer stran: navigace vzniká deterministicky ------------------- #
def test_predni_strana_ma_pismena_bez_cisel_karet():
    karta = Karta(cislo=7, nazev="X", typ=TypUzlu.POSTAVA, atmosfera="A" * 300,
                  uvod="Stojíš na rozcestí.",
                  volby=[Volba(text="Doleva k potoku", vysledek="Šplouchá", cil=8),
                         Volba(text="Doprava do houští", vysledek="Šustí", cil=9)])
    assert "A) Doleva k potoku" in karta.predni
    assert "B) Doprava do houští" in karta.predni
    assert "8" not in karta.predni and "9" not in karta.predni  # čísla až na zadní


def test_zadni_strana_ma_sipky_na_cile():
    karta = Karta(cislo=7, nazev="X", typ=TypUzlu.POSTAVA, atmosfera="A" * 300,
                  uvod="U.", zaver="Slyšíš kroky.",
                  volby=[Volba(text="t1", vysledek="Potok tě osvěží", cil=8),
                         Volba(text="t2", vysledek="Houští škrábe", cil=9)])
    assert "Slyšíš kroky." in karta.zadni
    assert "A) Potok tě osvěží → karta 8" in karta.zadni
    assert "B) Houští škrábe → karta 9" in karta.zadni


def test_predni_strana_zobrazuje_podminku():
    karta = Karta(cislo=5, nazev="X", typ=TypUzlu.STREZ, atmosfera="A" * 300,
                  uvod="Brána.",
                  volby=[Volba(text="Odemkni bránu", vysledek="Otevřeno", cil=6,
                               podminka="KLÍČ")])
    assert "(podmínka: KLÍČ)" in karta.predni


def test_varianta_30_filtruje_side_a_preciseluje_pismena():
    karta = Karta(cislo=2, nazev="X", typ=TypUzlu.ROZCESTI, atmosfera="A" * 300,
                  uvod="U.",
                  volby=[Volba(text="side akce", vysledek="side výsledek", cil=13, side=True),
                         Volba(text="core akce", vysledek="core výsledek", cil=3)])
    # 30min varianta: side volba zmizí a zbylá se přečísluje na A)
    assert "A) core akce" in karta.predni_30
    assert "side akce" not in karta.predni_30
    assert karta.zadni_30 == "A) core výsledek → karta 3"
    # 60min varianta má obě
    assert "A) side akce" in karta.predni and "B) core akce" in karta.predni


def test_cilova_karta_bez_voleb_ma_zaver():
    karta = Karta(cislo=12, nazev="Cíl", typ=TypUzlu.CIL, atmosfera="A" * 300,
                  uvod="Finále.", zaver="Organizátor přečte epilog.")
    assert karta.zadni == "Organizátor přečte epilog."
    assert karta.zadni_30 is None


# ------- prompt: cíle vyjmenované, count vynucený --------------------------- #
def test_prompt_vyjmenuje_cile_v_poradi_hran(valid_mapa, valid_zadani):
    from honbicka.orchestrator import _kontext_karty
    uzel7 = valid_mapa.uzel(7)  # hrany → [8, 9]
    kontext = _kontext_karty(valid_mapa, uzel7)
    prompt = _prompt_vypravec(valid_zadani, _koncept(), uzel7, kontext)
    assert "PŘESNĚ 2" in prompt
    assert "1. volba vede na kartu" in prompt and "2. volba vede na kartu" in prompt
    assert "NIKDY nepiš šipky" in prompt


def test_prompt_cilove_karty_zada_prazdne_volby(valid_mapa, valid_zadani):
    from honbicka.orchestrator import _kontext_karty
    cil = next(u for u in valid_mapa.uzly if u.typ == TypUzlu.CIL)
    kontext = _kontext_karty(valid_mapa, cil)
    prompt = _prompt_vypravec(valid_zadani, _koncept(), cil, kontext)
    assert "prázdný seznam" in prompt and "epilog" in prompt


def test_prompt_oprava_poctu_voleb(valid_mapa, valid_zadani):
    from honbicka.orchestrator import _kontext_karty
    uzel7 = valid_mapa.uzel(7)
    kontext = _kontext_karty(valid_mapa, uzel7)
    prompt = _prompt_vypravec(valid_zadani, _koncept(), uzel7, kontext,
                              oprava_poctu_voleb=True)
    assert "ŠPATNÝ POČET" in prompt


# ------- end-to-end napis_kartu --------------------------------------------- #
def test_napis_kartu_opravi_pocet_voleb_pres_retry(valid_mapa, valid_zadani):
    # 1. pokus: 1 volba na uzel se 2 hranami; 2. pokus: 2 volby → uspěje
    klient = FakeKlient(odpovedi=[_navrh_dict(1), _navrh_dict(2)])
    uzel = valid_mapa.uzel(7)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert [v.cil for v in karta.volby] == [8, 9]
    assert any(e.get("volby_pocet_chyba") == 1 for e in log)
    assert len(klient.prompty) == 2
    assert "ŠPATNÝ POČET" in klient.prompty[1]


def test_napis_kartu_doplni_volby_po_vycerpani_pokusu(valid_mapa, valid_zadani):
    # model 3× vrátí málo voleb → poslední záchrana: doplnění generických voleb
    klient = FakeKlient(cyklus=_navrh_dict(1))
    uzel = valid_mapa.uzel(7)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert len(klient.prompty) == MAX_ITERACI_KARTA
    assert [v.cil for v in karta.volby] == [8, 9]  # navigace úplná i tak
    assert any(e.get("volby_doplneny_deterministicky") for e in log)


def test_napis_kartu_prebytek_voleb_projde_na_prvni_pokus(valid_mapa, valid_zadani):
    # 3 volby na uzel s 1 hranou → tiché oříznutí, žádný opravný prompt
    klient = FakeKlient(odpovedi=[_navrh_dict(3)])
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert len(klient.prompty) == 1
    assert [v.cil for v in karta.volby] == [10, 10]


# ------- O6: nouzová karta má platnou navigaci ----------------------------- #
def test_nouzova_karta_ma_volby_z_grafu_jedna_hrana(valid_mapa):
    uzel = valid_mapa.uzel(8)  # jediná hrana → 10
    karta = _nouzova_karta(uzel, _koncept(), valid_mapa)
    assert [v.cil for v in karta.volby] == [10, 10]
    assert "→ karta 10" in karta.zadni


def test_nouzova_karta_ma_volby_z_grafu_vice_hran(valid_mapa):
    uzel = valid_mapa.uzel(7)  # dvě hrany → [8, 9]
    karta = _nouzova_karta(uzel, _koncept(), valid_mapa)
    assert [v.cil for v in karta.volby] == [8, 9]


def test_nouzova_karta_cilova_karta_bez_voleb(valid_mapa):
    cil = next(u for u in valid_mapa.uzly if u.typ == TypUzlu.CIL)
    karta = _nouzova_karta(cil, _koncept(), valid_mapa)
    assert karta.volby == []
    assert "epilog" in karta.zadni.lower()


def test_nouzova_karta_side_volba_dostane_flag(valid_mapa):
    valid_mapa.uzel(4).profil = Profil.SIDE
    uzel = valid_mapa.uzel(2)  # hrany → [3, 4(SIDE)]
    karta = _nouzova_karta(uzel, _koncept(), valid_mapa)
    assert karta.zadni_30 is not None
    assert "→ karta 3" in karta.zadni_30 and "→ karta 4" not in karta.zadni_30


def test_napis_kartu_nouzova_karta_po_vycerpani_schema_pokusu(valid_mapa, valid_zadani):
    # model 3× vrátí nepoužitelný obsah (chybí povinná pole) → nouzová karta
    # s navigací složenou z grafu.
    klient = FakeKlient(cyklus={"nesmysl": True})
    uzel = valid_mapa.uzel(8)
    karta, fits, log = napis_kartu(klient, valid_zadani, _koncept(), valid_mapa, uzel,
                                   measurer=measurer_dle_delky)
    assert any(e.get("nouzova_karta") for e in log)
    assert [v.cil for v in karta.volby] == [10, 10]
