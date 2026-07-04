"""Testy škálovacích počtů (M2)."""

from honbicka.modely import Obtiznost, TypUzlu, VekPasmo, Zadani
from honbicka.validatory.skalovani import komponenty_rozsah, zkontroluj_skalovani


def test_valid_30min_projde(valid_mapa, valid_zadani):
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert v.ok, v.chyby


def test_neznamy_profil(valid_mapa, valid_zadani):
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 90)
    assert not v.ok


def test_malo_karet(valid_mapa, valid_zadani):
    valid_mapa.uzly = valid_mapa.uzly[:5]  # 5 < 8
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("počet karet" in c for c in v.chyby)


def test_chybejici_gated(valid_mapa, valid_zadani):
    valid_mapa.uzel(6).typ = TypUzlu.PRECHOD  # gated → 0
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("gated" in c for c in v.chyby)


def test_prah_neni_nasobek_5(valid_mapa, valid_zadani):
    valid_mapa.prah_aktivity = 97
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("práh" in c for c in v.chyby)


def test_prah_mimo_rozsah(valid_mapa, valid_zadani):
    valid_mapa.prah_aktivity = 125
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok


def test_kostka_podil_mimo(valid_mapa, valid_zadani):
    for u in valid_mapa.uzly:
        u.kostka = True  # 100 %
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("kostk" in c for c in v.chyby)


def test_vekovy_strop_teorie(valid_mapa):
    z = Zadani(vek=VekPasmo.V06_09, format_hracu="dvojice")  # strop
    v = zkontroluj_skalovani(valid_mapa, z, 30, falesne_teorie=2)
    assert not v.ok
    assert any("teorií" in c for c in v.chyby)


def test_vekovy_strop_konce(valid_mapa):
    z = Zadani(vek=VekPasmo.V04_06)  # strop
    v = zkontroluj_skalovani(valid_mapa, z, 30, konce=3)
    assert not v.ok
    assert any("konc" in c for c in v.chyby)


def test_pravdive_stopy_pod_minimem(valid_mapa, valid_zadani):
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30, pravdive_stopy=1)
    assert not v.ok
    assert any("stop" in c for c in v.chyby)


def test_koncept_pocty_none_se_preskoci(valid_mapa, valid_zadani):
    # bez koncept-počtů projde
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert v.ok, v.chyby


def test_komponenty_rozsah_dle_obtiznosti():
    assert komponenty_rozsah(30, Obtiznost.TEZKA) == (2, 2)
    assert komponenty_rozsah(60, Obtiznost.LEHKA) == (2, 3)
    assert komponenty_rozsah(60, Obtiznost.STREDNI) == (3, 4)
    assert komponenty_rozsah(60, Obtiznost.TEZKA) == (4, 5)
