"""Testy simulace průchodů (M2)."""

from honbicka.modely import Archetyp, VekPasmo, Zadani
from honbicka.validatory.simulace import (
    pasmo_aha,
    povinne_uzly,
    simuluj,
    zkontroluj_simulaci,
)


def test_pasmo_aha_archetypy():
    assert pasmo_aha(Archetyp.A1, False) == (65.0, 80.0)
    assert pasmo_aha(Archetyp.A2, False) == (68.0, 85.0)
    # volný formát: +7 p. b. k horní mezi
    assert pasmo_aha(Archetyp.A1, True) == (65.0, 87.0)
    assert pasmo_aha(Archetyp.A2, True) == (68.0, 92.0)


def test_povinne_uzly(valid_mapa):
    povinne = povinne_uzly(valid_mapa)
    # 8 (postava/AHA) je dominátor cíle; 9 (slepá) NENÍ povinná
    assert 8 in povinne
    assert 9 not in povinne


def test_valid_simulace_projde(valid_mapa, valid_zadani):
    reporty = simuluj(valid_mapa, valid_zadani, 30, pocet=5, seed=1)
    assert all(r.dosahl_cile for r in reporty)
    v = zkontroluj_simulaci(valid_mapa, valid_zadani, 30, reporty)
    assert v.ok, v.chyby


def test_aha_mimo_pasmo_prilis_brzy(valid_mapa, valid_zadani):
    valid_mapa.pozice_aha_uzel = 2  # AHA hned na začátku
    reporty = simuluj(valid_mapa, valid_zadani, 30, pocet=5, seed=1)
    v = zkontroluj_simulaci(valid_mapa, valid_zadani, 30, reporty)
    assert not v.ok
    assert any("AHA" in c for c in v.chyby)
    # diagnostika pro architekta obsahuje konkrétní %
    assert any("%" in d for d in v.diagnostika)


def test_klicove_svedectvi_mimo_povinnou_trasu(valid_mapa, valid_zadani):
    # přesuneme klíčové svědectví na slepou (9), která není povinná
    valid_mapa.uzel(8).klicove_svedectvi = False
    valid_mapa.uzel(9).klicove_svedectvi = True
    reporty = simuluj(valid_mapa, valid_zadani, 30, pocet=5, seed=1)
    v = zkontroluj_simulaci(valid_mapa, valid_zadani, 30, reporty)
    assert not v.ok
    assert any("povinné trase" in c for c in v.chyby)


def test_aha_uzel_neni_povinny(valid_mapa, valid_zadani):
    valid_mapa.pozice_aha_uzel = 9  # slepá, ne povinná
    reporty = simuluj(valid_mapa, valid_zadani, 30, pocet=5, seed=1)
    v = zkontroluj_simulaci(valid_mapa, valid_zadani, 30, reporty)
    assert not v.ok


def test_simulace_je_deterministicka(valid_mapa, valid_zadani):
    a = simuluj(valid_mapa, valid_zadani, 30, pocet=5, seed=42)
    b = simuluj(valid_mapa, valid_zadani, 30, pocet=5, seed=42)
    assert [r.delka_min for r in a] == [r.delka_min for r in b]


def test_volny_format_prvni_navsteva(valid_mapa):
    # volný formát zkracuje opakované návštěvy → nikdy delší než ne-volný
    z_volny = Zadani(vek=VekPasmo.V09_12, format_hracu="volny_format")
    z_pevny = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice")
    dv = [r.delka_min for r in simuluj(valid_mapa, z_volny, 30, pocet=5, seed=3)]
    dp = [r.delka_min for r in simuluj(valid_mapa, z_pevny, 30, pocet=5, seed=3)]
    assert sum(dv) <= sum(dp)
