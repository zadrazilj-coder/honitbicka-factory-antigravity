"""Testy datových modelů (M1)."""

import pytest
from pydantic import ValidationError

from honbicka.modely import (
    SCHEMA_KARTA,
    SCHEMA_MAPA,
    SCHEMA_REDAKCE,
    SCHEMA_ZADANI,
    Archetyp,
    Hrana,
    Mapa,
    Pravdivost,
    Profil,
    TypUzlu,
    Uzel,
    VekPasmo,
    Zadani,
)


def test_zadani_minimalni():
    z = Zadani(vek=VekPasmo.V06_09)
    assert z.tema is None
    assert z.format_hracu == "volny_format"
    assert z.prostredi == ["les"]
    assert z.jazyk == "cs"
    assert z.je_volny_format is True


@pytest.mark.parametrize("fmt", ["jednotlivci", "dvojice", "volny_format", "tymy_4x4", "tymy_1x1"])
def test_format_hracu_platny(fmt):
    z = Zadani(vek=VekPasmo.V09_12, format_hracu=fmt)
    assert z.format_hracu == fmt


@pytest.mark.parametrize("fmt", ["tymy_5x4", "tymy_4x5", "tymy_0x2", "party", "tymy_2", "tymy_axb"])
def test_format_hracu_neplatny(fmt):
    with pytest.raises(ValidationError):
        Zadani(vek=VekPasmo.V09_12, format_hracu=fmt)


def test_rozmery_tymu():
    assert Zadani(vek=VekPasmo.V09_12, format_hracu="tymy_4x3").rozmery_tymu() == (4, 3)
    assert Zadani(vek=VekPasmo.V09_12, format_hracu="volny_format").rozmery_tymu() is None


def test_mapa_helpery():
    uzly = [
        Uzel(cislo=1, nazev="Start", typ=TypUzlu.ONBOARDING, region="les", prostredi="les",
             profil=Profil.CORE, hrany=[Hrana(cil=2)]),
        Uzel(cislo=2, nazev="Vedlejší", typ=TypUzlu.SBER, region="les", prostredi="les",
             profil=Profil.SIDE),
        Uzel(cislo=3, nazev="Cíl", typ=TypUzlu.CIL, region="les", prostredi="les",
             profil=Profil.CORE),
    ]
    mapa = Mapa(archetyp=Archetyp.A1, seed=42, prah_aktivity=100, pozice_aha_uzel=3,
                regiony=["les"], uzly=uzly)
    assert mapa.uzel(2).nazev == "Vedlejší"
    assert mapa.uzel(99) is None
    # 30min podgraf = jen CORE
    assert {u.cislo for u in mapa.core_uzly} == {1, 3}


# ------- MD2: Uzel.pravdivost ----------------------------------------------- #
def test_uzel_pravdivost_default_je_none():
    u = Uzel(cislo=1, nazev="X", typ=TypUzlu.INFORMACE, region="les", prostredi="les",
             profil=Profil.CORE)
    assert u.pravdivost is None


@pytest.mark.parametrize("hodnota", list(Pravdivost))
def test_uzel_pravdivost_prijima_enum(hodnota):
    u = Uzel(cislo=1, nazev="X", typ=TypUzlu.INFORMACE, region="les", prostredi="les",
             profil=Profil.CORE, pravdivost=hodnota)
    assert u.pravdivost == hodnota


def test_schemata_jsou_json_schema():
    for schema in (SCHEMA_ZADANI, SCHEMA_MAPA, SCHEMA_KARTA, SCHEMA_REDAKCE):
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"
        assert "properties" in schema
