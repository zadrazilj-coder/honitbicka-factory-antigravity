"""Testy FÁZE 0 — losování (M3). Losuje Python, deterministicky dle seedu."""

from honbicka.modely import Archetyp, VekPasmo, Zadani
from honbicka.orchestrator import losuj_parametry, pocty_cile
from honbicka.validatory.simulace import pasmo_aha


def _z(**kw):
    return Zadani(vek=kw.pop("vek", VekPasmo.V09_12), **kw)


def test_determinismus():
    z = _z()
    a = losuj_parametry(z, 12345)
    b = losuj_parametry(z, 12345)
    assert a == b


def test_prah_je_nasobek_5_v_rozsahu():
    z = _z()
    for seed in range(200):
        p = losuj_parametry(z, seed)
        assert p.prah_aktivity % 5 == 0
        assert 80 <= p.prah_aktivity <= 120


def test_pocet_karet_v_rozsahu_60():
    z = _z()
    for seed in range(100):
        p = losuj_parametry(z, seed)
        assert 18 <= p.pocet_karet_60 <= 25


def test_pozice_aha_v_pasmu_archetypu():
    z = _z(format_hracu="dvojice")
    for seed in range(100):
        p = losuj_parametry(z, seed)
        low, high = pasmo_aha(p.archetyp, z.je_volny_format)
        assert low <= p.pozice_aha_pct <= high


def test_okno_zakazu_archetypu():
    z = _z()
    zakazane = frozenset({a for a in Archetyp if a != Archetyp.A3})
    for seed in range(50):
        p = losuj_parametry(z, seed, zakazane)
        assert p.archetyp == Archetyp.A3


def test_vahy_preferuji_caste_archetypy():
    z = _z()
    from collections import Counter
    c = Counter(losuj_parametry(z, s).archetyp for s in range(600))
    # A1 (váha 30) výrazně častější než A6 (váha 9)
    assert c[Archetyp.A1] > c[Archetyp.A6]


def test_pocty_cile_vekovy_strop():
    bez = pocty_cile(_z(vek=VekPasmo.V12_15))
    se = pocty_cile(_z(vek=VekPasmo.V06_09))
    assert bez["falesne_teorie"] == 2 and bez["konce"] == 3
    assert se["falesne_teorie"] == 1 and se["konce"] == 2
