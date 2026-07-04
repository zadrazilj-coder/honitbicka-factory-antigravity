"""Deterministický graf-scaffolder (FÁZE 1 bez LLM).

Zjištění M8: 27B model nespolehlivě splní tvrdé topologické invarianty
(souvislost, dominátory klíčových svědectví/AHA, validita CORE podgrafu). Dle
zásady spec §3 „LLM tvoří, Python rozhoduje" tu STRUKTURU vlastní Python:
`postav_skeleton` vygeneruje graf, který projde `validuj_par_30_60` z KONSTRUKCE.
LLM (koncept + vypravěč) pak dodá jen OBSAH (téma, teorie, texty karet).

Topologie: CORE trunk (12 uzlů = hratelná 30min hra) + SIDE region (jen 60min),
který se sbíhá zpět do trunku PŘED AHA uzlem, takže AHA i klíčové svědectví
zůstávají dominátory obou grafů. AHA uzel se vybírá adaptivně, aby jeho pozice
(v čase) padla do pásma archetypu pro 30min i 60min profil.
"""

from __future__ import annotations

import random
import statistics

from honbicka.modely import Hrana, Koncept, Mapa, Profil, TypUzlu, Uzel, Zadani
from honbicka.orchestrator import LosovaneParametry
from honbicka.validatory.simulace import pasmo_aha, povinne_uzly, simuluj
from honbicka.validatory.skalovani import komponenty_rozsah

AHA_UZEL_DEFAULT = 10  # prechod mezi rozcestím (7) a postavou (8) ~ 70 %


def _regiony(zadani: Zadani) -> tuple[str, str]:
    prost = [p for p in (zadani.prostredi or []) if p] or ["les"]
    reg_a = prost[0]
    reg_b = prost[1] if len(prost) > 1 else ("potok" if reg_a != "potok" else "louka")
    return reg_a, reg_b


# Počet simulačních průchodů (spec „≥5"). 15 dává stabilní medián pozice AHA
# (5 průchodů je pro výběr uzlu příliš šumivé). Pipeline musí validovat stejným
# počtem — viz orchestrator.vyrob_hru (pouzij_scaffolder).
POCET_SIMULACI = 15


def _median_aha(mapa: Mapa, zadani: Zadani, profil: int, uzel: int) -> float | None:
    mapa.pozice_aha_uzel = uzel
    pcts = [r.pozice_aha_pct for r in simuluj(mapa, zadani, profil, pocet=POCET_SIMULACI)
            if r.pozice_aha_pct >= 0]
    return statistics.median(pcts) if pcts else None


def _vyber_aha_uzel(mapa: Mapa, zadani: Zadani) -> int:
    """Vybere uzel na povinné trase, jehož mediánová pozice AHA (v čase) je
    nejblíž STŘEDU pásma pro 60min i 30min zároveň — nejbezpečnější vůči
    variabilitě simulace (ne krajní hodnota pásma). Deterministické."""
    low, high = pasmo_aha(mapa.archetyp, zadani.je_volny_format)
    stred = (low + high) / 2
    core = mapa.podgraf_core()
    core_cisla = {u.cislo for u in core.uzly}
    kandidati = sorted(
        d for d in povinne_uzly(mapa)
        if d in core_cisla
        and (u := mapa.uzel(d)) is not None and u.typ not in (TypUzlu.ONBOARDING, TypUzlu.CIL)
    )
    nejlepsi, nejlepsi_skore = AHA_UZEL_DEFAULT, 1e18
    for d in kandidati:
        m60 = _median_aha(mapa, zadani, 60, d)
        m30 = _median_aha(core, zadani, 30, d)
        if m60 is None or m30 is None:
            continue
        # skóre = nejhorší vzdálenost od středu → preferuje centrovaný uzel
        skore = max(abs(m60 - stred), abs(m30 - stred))
        if skore < nejlepsi_skore:
            nejlepsi_skore, nejlepsi = skore, d
    return nejlepsi


def postav_skeleton(
    zadani: Zadani, koncept: Koncept, params: LosovaneParametry,
    rng: random.Random | None = None,
) -> Mapa:
    """Vrátí validní mapu (projde validuj_par_30_60) pro daný archetyp/obtížnost."""
    reg_a, reg_b = _regiony(zadani)
    # Scaffolder vlastní strukturu: pevných 21 uzlů (12 CORE + 9 SIDE) — v pásmu
    # 18–25 a bez proměnného SIDE fillru, který by rozkolísal 60min pozici AHA.
    komp_min = komponenty_rozsah(60, zadani.obtiznost)[0]
    komp = [f"díl artefaktu {i + 1}" for i in range(komp_min)]

    uzly: list[Uzel] = []
    C, S, T = Profil.CORE, Profil.SIDE, TypUzlu

    def add(cislo, typ, region, hrany, profil, *, kostka=False, komp_=None):
        uzly.append(Uzel(
            cislo=cislo, nazev=f"{typ.value} {cislo}", typ=typ, region=region,
            prostredi=region, profil=profil, kostka=kostka, komponenty=komp_ or [],
            klicove_svedectvi=False, hrany=[Hrana(cil=c) for c in hrany],
        ))

    # --- CORE trunk (region A), uzly 1..12 = hratelná 30min hra ---------- #
    add(1, T.ONBOARDING, reg_a, [2], C)
    add(2, T.ROZCESTI, reg_a, [3, 4, 13], C, kostka=True)   # 13 = jediný vstup do SIDE
    add(3, T.INFORMACE, reg_a, [5], C)
    add(4, T.INFORMACE, reg_a, [5], C)
    add(5, T.STREZ, reg_a, [6], C, kostka=True)
    add(6, T.GATED, reg_a, [7], C, komp_=[komp[0]])
    add(7, T.ROZCESTI, reg_a, [10, 9], C, kostka=True)      # větev: trunk (10) / slepá (9)
    add(8, T.POSTAVA, reg_a, [11], C, komp_=[komp[1]])      # postava (za AHA uzlem)
    add(9, T.SLEPA, reg_a, [7], C)
    add(10, T.PRECHOD, reg_a, [8], C)                       # dominátor mezi 7 a 8 (~AHA)
    add(11, T.SMYCKA, reg_a, [12], C, kostka=True)
    add(12, T.CIL, reg_a, [], C)
    # --- SIDE region B (jen 60min), sbíhá se do uzlu 7 před AHA ---------- #
    add(13, T.ROZCESTI, reg_b, [14, 15], S, kostka=True)
    add(14, T.SBER, reg_b, [16], S, kostka=True)
    add(15, T.SLEPA, reg_b, [13], S)
    add(16, T.STREZ, reg_b, [17], S, komp_=([komp[2]] if komp_min > 2 else None))
    add(17, T.INFORMACE, reg_b, [18], S, kostka=True)
    add(18, T.GATED, reg_b, [19], S, komp_=([komp[3]] if komp_min > 3 else None))
    add(19, T.OBCHODNIK, reg_b, [20], S)
    add(20, T.SMYCKA, reg_b, [21], S)
    add(21, T.JEDNOSMER, reg_b, [7], S)                     # návrat do CORE (uzel 7)

    mapa = Mapa(archetyp=params.archetyp, seed=params.seed,
                prah_aktivity=params.prah_aktivity, pozice_aha_uzel=AHA_UZEL_DEFAULT,
                regiony=[reg_a, reg_b], uzly=uzly)
    mapa.uzel(11).hrany[0].jednosmerna = True  # 11→12 jednosměrka (2. jednosměrka)

    # Adaptivní AHA uzel (v pásmu pro oba profily) + klíčové svědectví na týž uzel.
    aha = _vyber_aha_uzel(mapa, zadani)
    mapa.pozice_aha_uzel = aha
    for u in mapa.uzly:
        u.klicove_svedectvi = (u.cislo == aha)
    return mapa
