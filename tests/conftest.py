"""Sdílené fixtury pro testy validátorů (M2).

`valid_mapa()` staví malou, ale plně validní 30min mapu (CORE), která projde
topologií, škálováním i simulací. Negativní testy si ji kopírují a rozbíjejí.
"""

from __future__ import annotations

import pytest

from honbicka.modely import (
    Archetyp,
    Hrana,
    Mapa,
    Obtiznost,
    Profil,
    TypUzlu,
    Uzel,
    VekPasmo,
    Zadani,
)


def _u(cislo, typ, hrany, *, region="les", prostredi="les", kostka=False,
       komponenty=None, klicove=False):
    return Uzel(
        cislo=cislo, nazev=f"Uzel {cislo}", typ=typ, region=region, prostredi=prostredi,
        profil=Profil.CORE, kostka=kostka, komponenty=komponenty or [],
        klicove_svedectvi=klicove, hrany=[Hrana(cil=c) for c in hrany],
    )


def build_valid_mapa() -> Mapa:
    """11 uzlů, 30min CORE. AHA na uzlu 8 (postava, povinná trasa).

    Uzly 2/7 jsou POSTAVA místo generického rozcestí (SC1/V1: postavy 30min
    3–4) — bezpečný retyp, „větve" se počítají z hran (≥2), ne z typu."""
    uzly = [
        _u(1, TypUzlu.ONBOARDING, [2]),
        _u(2, TypUzlu.POSTAVA, [3, 4], kostka=True),     # fork1 (rejoin v 5)
        _u(3, TypUzlu.INFORMACE, [5]),
        _u(4, TypUzlu.INFORMACE, [5]),
        _u(5, TypUzlu.STREZ, [6], kostka=True),          # střežená
        _u(6, TypUzlu.GATED, [7], komponenty=["klic"]),  # gated + komponenta
        _u(7, TypUzlu.POSTAVA, [8, 9], kostka=True),     # fork2
        _u(8, TypUzlu.POSTAVA, [10], komponenty=["kvetina"], klicove=True),  # AHA
        _u(9, TypUzlu.SLEPA, [7]),                        # slepá (návrat do 7)
        _u(10, TypUzlu.SMYCKA, [11], kostka=True),       # smyčka (typově)
        _u(11, TypUzlu.CIL, []),
    ]
    # jednosměrka: hrana 10→11
    uzly[9].hrany[0].jednosmerna = True
    return Mapa(archetyp=Archetyp.A1, seed=7, prah_aktivity=100,
                pozice_aha_uzel=8, regiony=["les"], uzly=uzly)


def build_valid_mapa_60() -> Mapa:
    """20 uzlů: 11 CORE (les) tvoří validní 30min hru + 9 SIDE (potok) pro 60min.
    AHA na uzlu 8; všechny cesty (i SIDE) se sbíhají v uzlu 7 před AHA.

    Uzly 2/7 (CORE) a 13 (SIDE) jsou POSTAVA, uzel 12 (SIDE) je LECITEL
    (SC1/V1: postavy 30min 3–4, 60min 5–7 — postava+lecitel dohromady).
    Bezpečný retyp: „větve" se počítají z hran (≥2), ne z typu."""
    def s(cislo, typ, hrany, **kw):  # SIDE helper (region potok)
        u = _u(cislo, typ, hrany, region="potok", prostredi="potok", **kw)
        u.profil = Profil.SIDE
        return u

    uzly = [
        _u(1, TypUzlu.ONBOARDING, [2]),
        _u(2, TypUzlu.POSTAVA, [3, 4, 12], kostka=True),    # větev do SIDE (12)
        _u(3, TypUzlu.INFORMACE, [5]),
        _u(4, TypUzlu.INFORMACE, [5]),
        _u(5, TypUzlu.STREZ, [6], kostka=True),
        _u(6, TypUzlu.GATED, [7], komponenty=["klic"]),
        _u(7, TypUzlu.POSTAVA, [8, 9, 15], kostka=True),    # větev do SIDE (15)
        _u(8, TypUzlu.POSTAVA, [10], komponenty=["kvetina"], klicove=True),  # AHA
        _u(9, TypUzlu.SLEPA, [7]),
        _u(10, TypUzlu.SMYCKA, [11], kostka=True),
        _u(11, TypUzlu.CIL, []),
        # SIDE region „potok" (12–20) — sbíhá se zpět do uzlu 7 (před AHA)
        s(12, TypUzlu.LECITEL, [13, 14], kostka=True),
        s(13, TypUzlu.POSTAVA, [16], kostka=True),
        s(14, TypUzlu.SLEPA, [12]),
        s(15, TypUzlu.STREZ, [17]),
        s(16, TypUzlu.INFORMACE, [18], kostka=True),
        s(17, TypUzlu.GATED, [18]),
        s(18, TypUzlu.OBCHODNIK, [19]),
        s(19, TypUzlu.SMYCKA, [20]),
        s(20, TypUzlu.JEDNOSMER, [7]),
    ]
    uzly[9].hrany[0].jednosmerna = True  # 10→11 jednosměrka
    return Mapa(archetyp=Archetyp.A1, seed=7, prah_aktivity=100,
                pozice_aha_uzel=8, regiony=["les", "potok"], uzly=uzly)


@pytest.fixture
def valid_mapa() -> Mapa:
    return build_valid_mapa()


@pytest.fixture
def valid_mapa_60() -> Mapa:
    return build_valid_mapa_60()


@pytest.fixture
def valid_zadani() -> Zadani:
    # ne-volný formát → pásmo AHA 65–80 %
    return Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", obtiznost=Obtiznost.LEHKA)
