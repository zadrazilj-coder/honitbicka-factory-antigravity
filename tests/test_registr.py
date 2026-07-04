"""Testy registru her + okna zákazů (M6)."""

from honbicka.modely import Archetyp
from honbicka.registr import (
    ZaznamRegistru,
    nacti_registr,
    zakazana_okna,
    zakazane_archetypy,
    zapis_zaznam,
)


def _z(slug, archetyp, mechanismus, rekvizity, seed):
    return ZaznamRegistru(datum="2026-07-04", slug=slug, archetyp=archetyp,
                          mechanismus=mechanismus, rekvizity=rekvizity,
                          zanr_publikum="humor/09-12", profily="30+60", seed=seed)


def test_chybejici_soubor_je_prazdny(tmp_path):
    assert nacti_registr(str(tmp_path / "neni.md")) == []


def test_zapis_a_round_trip(tmp_path):
    cesta = str(tmp_path / "registr.md")
    zapis_zaznam(_z("hra-a", "A1", "průnik stop", "sítko, mapa", 11), cesta)
    zapis_zaznam(_z("hra-b", "A3", "zadavatel lže", "dopis", 22), cesta)
    zaznamy = nacti_registr(cesta)
    assert [z.slug for z in zaznamy] == ["hra-a", "hra-b"]
    assert zaznamy[0].archetyp == "A1" and zaznamy[0].seed == 11
    assert zaznamy[1].mechanismus == "zadavatel lže"


def test_pipe_v_obsahu_nerozbije_tabulku(tmp_path):
    cesta = str(tmp_path / "registr.md")
    zapis_zaznam(_z("hra|x", "A1", "a|b", "c|d", 1), cesta)
    zaznamy = nacti_registr(cesta)
    assert len(zaznamy) == 1  # tabulka zůstala validní


def test_okna_zakazu():
    zaznamy = [_z(f"h{i}", a, f"mech{i}", f"rek{i}", i)
               for i, a in enumerate(["A1", "A2", "A3", "A4", "A5", "A6"])]
    okna = zakazana_okna(zaznamy)
    # archetyp z posl. 3 → A4,A5,A6
    assert okna["archetyp"] == {"A4", "A5", "A6"}
    # mechanismus/rekvizity z posl. 5
    assert "mech5" in okna["mechanismus"] and "mech0" not in okna["mechanismus"]
    assert "rek1" in okna["rekvizity"] and "rek0" not in okna["rekvizity"]


def test_zakazane_archetypy_typovane():
    zaznamy = [_z("h1", "A1", "m", "r", 1), _z("h2", "A7", "m", "r", 2)]
    zak = zakazane_archetypy(zaznamy)
    assert Archetyp.A1 in zak and Archetyp.A7 in zak
