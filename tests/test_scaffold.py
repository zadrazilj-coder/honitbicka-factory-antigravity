"""Testy deterministického scaffolderu (FÁZE 1 bez LLM)."""

import pytest

from honbicka.modely import (
    Archetyp,
    Koncept,
    Obtiznost,
    Pravdivost,
    Profil,
    TypUzlu,
    VekPasmo,
    Zadani,
)
from honbicka.orchestrator import losuj_parametry, pocty_cile
from honbicka.scaffold import POCET_SIMULACI, postav_skeleton
from honbicka.validatory.agregace import validuj_par_30_60
from honbicka.validatory.simulace import POCET_SIMULACI_DEFAULT, povinne_uzly


# ------- V4: scaffolder a validátor default sdílí JEDEN zdroj počtu simulací #
def test_pocet_simulaci_je_sjednoceny_s_validatorem():
    assert POCET_SIMULACI == POCET_SIMULACI_DEFAULT


def _koncept(zadani, params):
    c = pocty_cile(zadani)
    return Koncept(archetyp=params.archetyp, tema="Kapka vody", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                   falesne_teorie=c["falesne_teorie"], pravdive_stopy=c["pravdive_stopy"],
                   konce=c["konce"])


def _skeleton(vek=VekPasmo.V09_12, fmt="dvojice", obt=Obtiznost.LEHKA, seed=0,
              prostredi=None):
    zad = Zadani(vek=vek, format_hracu=fmt, obtiznost=obt, tema="Kapka vody",
                 prostredi=prostredi or ["les", "potok"])
    params = losuj_parametry(zad, seed)
    kon = _koncept(zad, params)
    return zad, kon, params, postav_skeleton(zad, kon, params)


@pytest.mark.parametrize("obt", list(Obtiznost))
@pytest.mark.parametrize("fmt", ["dvojice", "volny_format", "tymy_4x4", "jednotlivci"])
def test_skeleton_projde_validaci(obt, fmt):
    # projít napříč seedy (pokrývá různé archetypy a jejich AHA pásma)
    for seed in range(14):
        zad, kon, params, mapa = _skeleton(fmt=fmt, obt=obt, seed=seed)
        v, _ = validuj_par_30_60(mapa, zad, kon, pocet_simulaci=POCET_SIMULACI)
        assert v.ok, (fmt, obt.value, seed, params.archetyp.value, v.chyby)


def test_pokryva_vsechny_archetypy():
    videno = set()
    for seed in range(60):
        _, _, params, _ = _skeleton(seed=seed)
        videno.add(params.archetyp)
    assert videno == set(Archetyp)


def test_vekovy_strop_projde():
    for vek in (VekPasmo.V04_06, VekPasmo.V06_09):
        zad, kon, _, mapa = _skeleton(vek=vek, seed=3)
        v, _ = validuj_par_30_60(mapa, zad, kon, pocet_simulaci=POCET_SIMULACI)
        assert v.ok, v.chyby


def test_struktura():
    _, _, _, mapa = _skeleton()
    assert len(mapa.uzly) == 21
    assert len(mapa.core_uzly) == 12
    # AHA uzel je na povinné trase (dominátor) a nese klíčové svědectví
    assert mapa.pozice_aha_uzel in povinne_uzly(mapa)
    klic = [u.cislo for u in mapa.uzly if u.klicove_svedectvi]
    assert klic == [mapa.pozice_aha_uzel]


def test_deterministicky():
    a = _skeleton(seed=7)[3]
    b = _skeleton(seed=7)[3]
    assert a.model_dump() == b.model_dump()


def test_postavy_a_lecitel_dle_skalovani():
    # SC1/V1: 30min (CORE) potřebuje 3-4 postav, 60min (celý graf) 5-7
    # (postava+lecitel dohromady; engine dřív úplně chyběl léčitel v mapě).
    _, _, _, mapa = _skeleton()
    core = mapa.core_uzly

    def pocet_postav(uzly):
        return sum(1 for u in uzly if u.typ in (TypUzlu.POSTAVA, TypUzlu.LECITEL))

    core_postavy = pocet_postav(core)
    plny_postavy = pocet_postav(mapa.uzly)
    assert 3 <= core_postavy <= 4, core_postavy
    assert 5 <= plny_postavy <= 7, plny_postavy
    # léčitel musí v mapě existovat (engine: stavy „vždy léčitelné")
    assert any(u.typ == TypUzlu.LECITEL for u in mapa.uzly)


def test_komponenty_dle_obtiznosti():
    # 60min: lehka 2, stredni 3, tezka 4 komponent; CORE vždy 2
    for obt, ocek in [(Obtiznost.LEHKA, 2), (Obtiznost.STREDNI, 3), (Obtiznost.TEZKA, 4)]:
        _, _, _, mapa = _skeleton(obt=obt)
        komp_all = {k for u in mapa.uzly for k in u.komponenty}
        komp_core = {k for u in mapa.uzly if u.profil == Profil.CORE for k in u.komponenty}
        assert len(komp_all) == ocek
        assert len(komp_core) == 2


# ------- MD2: pravdivost INFORMACE uzlů dle koncept-počtu -------------------- #
def test_informacni_uzly_dostanou_pravdivost_podle_konceptu():
    # výchozí _koncept() dává pravdive_stopy = pravdive_stopy_min(60min) = 3,
    # přesně tolik, kolik má pevná kostra INFORMACE uzlů (3, 4, 17) → všechny PRAVDA
    _, _, _, mapa = _skeleton()
    informacni = [u for u in mapa.uzly if u.typ == TypUzlu.INFORMACE]
    assert len(informacni) == 3
    assert all(u.pravdivost == Pravdivost.PRAVDA for u in informacni)


def test_informacni_uzly_zbytek_je_lez_nebo_zavadejici_kdyz_nestaci_pravda():
    zad = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody",
                 prostredi=["les", "potok"])
    params = losuj_parametry(zad, 0)
    kon = Koncept(archetyp=params.archetyp, tema="Kapka vody",
                  mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                  falesne_teorie=2, pravdive_stopy=1, konce=2)
    mapa = postav_skeleton(zad, kon, params)
    informacni = sorted((u for u in mapa.uzly if u.typ == TypUzlu.INFORMACE),
                        key=lambda u: u.cislo)
    assert [u.pravdivost for u in informacni].count(Pravdivost.PRAVDA) == 1
    assert all(u.pravdivost in (Pravdivost.LEZ, Pravdivost.ZAVADEJICI)
              for u in informacni if u.pravdivost != Pravdivost.PRAVDA)
