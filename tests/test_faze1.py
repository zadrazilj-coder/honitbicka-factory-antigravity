"""Testy FÁZE 1 — architekt + opravná smyčka (M3), s mockovaným klientem."""

import pytest
from pydantic import ValidationError

from honbicka.modely import Archetyp, Koncept, Mapa
from honbicka.orchestrator import (
    MAX_ITERACI_ARCHITEKT,
    MAX_ITERACI_KONCEPT,
    MAX_RELOSOVANI,
    _normalizuj_koncept_data,
    faze1_architekt,
    faze1a_koncept,
    losuj_parametry,
)
from honbicka.validatory.agregace import validuj_mapu


class FakeKlient:
    """Duck-typed náhrada OllamaKlient: vrací frontu odpovědí, zaznamenává prompty."""

    def __init__(self, odpovedi=None, cyklus=None):
        self.odpovedi = list(odpovedi or [])
        self.cyklus = cyklus
        self.prompty: list[str] = []

    def generuj_json(self, role, uzivatel, schema, extra_system=None):
        self.prompty.append(uzivatel)
        if self.odpovedi:
            return self.odpovedi.pop(0)
        if self.cyklus is not None:
            return self.cyklus
        raise AssertionError("FakeKlient: došly odpovědi")


@pytest.fixture
def koncept():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                   falesne_teorie=1, pravdive_stopy=2, konce=2)


@pytest.fixture
def params(valid_zadani):
    return losuj_parametry(valid_zadani, 7)


def _validator_30(zadani, koncept):
    return lambda m: validuj_mapu(m, zadani, 30, koncept)[0]


def _dump(mapa: Mapa) -> dict:
    return mapa.model_dump(mode="json")


def test_uspech_na_prvni_pokus(valid_mapa, valid_zadani, koncept, params):
    klient = FakeKlient(odpovedi=[_dump(valid_mapa)])
    v = faze1_architekt(klient, valid_zadani, koncept, params,
                        validator=_validator_30(valid_zadani, koncept))
    assert v.ok
    assert v.iterace_celkem == 1
    assert v.reseedy == 0
    assert isinstance(v.mapa, Mapa)


def test_oprava_pak_uspech_predava_diagnostiku(valid_mapa, valid_zadani, koncept, params):
    rozbita = _dump(valid_mapa)
    rozbita["pozice_aha_uzel"] = 2  # AHA moc brzy → simulace vrátí diagnostiku s %
    klient = FakeKlient(odpovedi=[rozbita, _dump(valid_mapa)])
    v = faze1_architekt(klient, valid_zadani, koncept, params,
                        validator=_validator_30(valid_zadani, koncept))
    assert v.ok
    assert v.iterace_celkem == 2
    # druhý prompt architektovi obsahuje konkrétní opravnou diagnostiku
    assert "OPRAV" in klient.prompty[1]
    assert "%" in klient.prompty[1]


def test_schema_chyba_je_opravna_iterace(valid_mapa, valid_zadani, koncept, params):
    klient = FakeKlient(odpovedi=[{"uplne": "spatne"}, _dump(valid_mapa)])
    v = faze1_architekt(klient, valid_zadani, koncept, params,
                        validator=_validator_30(valid_zadani, koncept))
    assert v.ok
    assert v.iterace_celkem == 2
    assert "schéma" in klient.prompty[1]


def test_vycerpani_limitu_konci_failem(valid_mapa, valid_zadani, koncept, params):
    rozbita = _dump(valid_mapa)
    rozbita["pozice_aha_uzel"] = 2  # trvale mimo pásmo
    klient = FakeKlient(cyklus=rozbita)
    v = faze1_architekt(klient, valid_zadani, koncept, params,
                        validator=_validator_30(valid_zadani, koncept))
    assert not v.ok
    assert v.reseedy == MAX_RELOSOVANI
    # 4 iterace × (1 + 2 relosování) = 12
    assert v.iterace_celkem == MAX_ITERACI_ARCHITEKT * (MAX_RELOSOVANI + 1)
    # v logu jsou přesně MAX_RELOSOVANI relosování
    assert sum(1 for e in v.log if e.get("akce") == "relosovani") == MAX_RELOSOVANI


def test_faze1a_koncept(valid_zadani, params):
    data = {
        "archetyp": "A1", "tema": "Kapka vody", "zanr": "přírodní humor",
        "mechanismus_reseni": "průnik tří stop", "klicova_rekvizita": "sítko",
        "falesne_teorie": 2, "pravdive_stopy": 3, "konce": 3, "slovnik_zakazana": ["zabít"],
    }
    klient = FakeKlient(odpovedi=[data])
    k = faze1a_koncept(klient, valid_zadani, params)
    assert isinstance(k, Koncept)
    assert k.tema == "Kapka vody"
    assert k.falesne_teorie == 2


# ------- O5: plnohodnotný koncept (věty, ne snake_case tokeny) ------------- #
def _data_koncept(mechanismus="Průnik tří stop odhalí pravdu.", rekvizita="sítko"):
    return {
        "archetyp": "A1", "tema": "Kapka vody", "zanr": "přírodní humor",
        "mechanismus_reseni": mechanismus, "klicova_rekvizita": rekvizita,
        "falesne_teorie": 2, "pravdive_stopy": 3, "konce": 3, "slovnik_zakazana": [],
    }


def test_prompt_obsahuje_priklad_vety(valid_zadani, params):
    klient = FakeKlient(odpovedi=[_data_koncept()])
    faze1a_koncept(klient, valid_zadani, params)
    assert "KRITICKÉ" in klient.prompty[0]
    assert "Příklad DOBŘE" in klient.prompty[0]
    assert "drak_kyha_pyl" in klient.prompty[0]  # ukázka ŠPATNĚ pro kontrast


def test_koncept_zopakuje_po_snake_case_tokenu(valid_zadani, params):
    # 1. pokus: snake_case token (živě pozorováno) → 2. pokus: plná věta → OK
    klient = FakeKlient(odpovedi=[
        _data_koncept(mechanismus="prunik_stop"),
        _data_koncept(mechanismus="Průnik nezávislých stop odhalí pravdu."),
    ])
    k = faze1a_koncept(klient, valid_zadani, params)
    assert k.mechanismus_reseni == "Průnik nezávislých stop odhalí pravdu."
    assert len(klient.prompty) == 2
    assert "nevyhověla" in klient.prompty[1]


def test_koncept_mechanicka_oprava_po_vycerpani_pokusu(valid_zadani, params):
    # model vždy vrátí snake_case → po MAX_ITERACI_KONCEPT pokusech mechanická oprava
    klient = FakeKlient(cyklus=_data_koncept(mechanismus="prunik_stop_bez_vety"))
    k = faze1a_koncept(klient, valid_zadani, params)
    assert len(klient.prompty) == MAX_ITERACI_KONCEPT
    assert "_" not in k.mechanismus_reseni
    assert " " in k.mechanismus_reseni


def test_normalizuj_koncept_data_prazdny_mechanismus():
    opraveno = _normalizuj_koncept_data({"mechanismus_reseni": "", "klicova_rekvizita": ""})
    assert opraveno["mechanismus_reseni"]  # neprázdné, obecná fráze
    assert " " in opraveno["mechanismus_reseni"]


def test_normalizuj_koncept_data_odstrani_podtrzitko_z_rekvizity():
    opraveno = _normalizuj_koncept_data({"klicova_rekvizita": "vzacna_kvetina"})
    assert opraveno["klicova_rekvizita"] == "vzacna kvetina"


def test_koncept_odmitne_prilis_kratky_mechanismus():
    with pytest.raises(ValidationError):  # min_length
        Koncept(archetyp=Archetyp.A1, tema="X", mechanismus_reseni="krátce",
                falesne_teorie=1, pravdive_stopy=2, konce=2)


def test_koncept_odmitne_snake_case_i_kdyz_dost_dlouhy():
    with pytest.raises(ValidationError):
        Koncept(archetyp=Archetyp.A1, tema="X",
                mechanismus_reseni="toto_je_dost_dlouhy_snake_case_token",
                falesne_teorie=1, pravdive_stopy=2, konce=2)
