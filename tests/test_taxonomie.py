"""Testy taxonomie a mapování věkových pásem (M1)."""

import pytest

from honbicka.modely import VekPasmo, Zadani
from honbicka.taxonomie import VEK_FACTORY_NA_ENGINE, cesta_hotove_hry, vek_pro_engine


def test_mapovani_pokryva_vsechna_pasma():
    # každé factory pásmo má engine protějšek
    assert set(VEK_FACTORY_NA_ENGINE) == set(VekPasmo)


@pytest.mark.parametrize(
    "factory,engine",
    [("04-06", "4-6"), ("06-09", "7-10"), ("09-12", "11-14"),
     ("12-15", "15-18"), ("16plus", "dospeli")],
)
def test_vek_pro_engine(factory, engine):
    assert vek_pro_engine(VekPasmo(factory)) == engine


def test_cesta_hotove_hry():
    z = Zadani(vek=VekPasmo.V06_09, format_hracu="tymy_4x4")
    cesta = cesta_hotove_hry(z, "lesni-detektivka", 30)
    assert cesta == "hotove_hry/vek_06-09/tymy_4x4/lesni-detektivka_30min"


def test_cesta_hotove_hry_odmita_neplatny_profil():
    z = Zadani(vek=VekPasmo.V06_09)
    with pytest.raises(ValueError):
        cesta_hotove_hry(z, "x", 90)  # 90 min factory nepoužívá
