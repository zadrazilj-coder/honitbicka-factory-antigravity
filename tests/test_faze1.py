"""Testy FÁZE 1 — architekt + opravná smyčka (M3), s mockovaným klientem."""

import pytest

from honbicka.modely import Archetyp, Koncept, Mapa
from honbicka.orchestrator import (
    MAX_ITERACI_ARCHITEKT,
    MAX_RELOSOVANI,
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
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody", mechanismus_reseni="průnik stop",
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
