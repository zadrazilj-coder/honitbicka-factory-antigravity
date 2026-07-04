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


# ------- T3: postavy (SC1/V1) — chybějící řádek tabulky dřív nechytil ---- #
def test_malo_postav_30min(valid_mapa, valid_zadani):
    # valid_mapa má 3 postavy (uzly 2,7,8); rozbij na 1 → musí selhat na 30min (3-4)
    valid_mapa.uzel(2).typ = TypUzlu.ROZCESTI
    valid_mapa.uzel(7).typ = TypUzlu.ROZCESTI
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("postav" in c for c in v.chyby)


def test_lecitel_se_pocita_do_postav(valid_mapa, valid_zadani):
    # 1 postava (uzel 8) + přetypovaný uzel 2 na lecitel = 2 postavy — pořád málo (3-4)
    valid_mapa.uzel(2).typ = TypUzlu.LECITEL
    valid_mapa.uzel(7).typ = TypUzlu.ROZCESTI
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("postav" in c for c in v.chyby)


def test_prilis_mnoho_postav(valid_mapa, valid_zadani):
    # přetypuj i informační uzly na postavy → 5 postav, nad rozsahem 3-4
    valid_mapa.uzel(3).typ = TypUzlu.POSTAVA
    valid_mapa.uzel(4).typ = TypUzlu.POSTAVA
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert not v.ok
    assert any("postav" in c for c in v.chyby)


def test_obchodnik_se_nepocita_do_postav(valid_mapa, valid_zadani):
    # přetypování na obchodníka nesmí zvýšit "postavy" — pořád jen 3 (2,7,8)
    valid_mapa.uzel(9).typ = TypUzlu.OBCHODNIK  # slepá → obchodník (jen pro test)
    v = zkontroluj_skalovani(valid_mapa, valid_zadani, 30)
    assert v.ok, v.chyby  # 3 postavy (2,7,8) stále v rozsahu 3-4
