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

Postavy (SC1/V1): CORE má 3 uzly typu `postava` (7, 8, 10) — dost pro 30min
škálování (3–4). SIDE přidává `lecitel` (13, engine: stavy „vždy léčitelné")
a další `postava` (14) — 60min tak má postavy+lecitel = 5 (škálování 5–7).
"""

from __future__ import annotations

import random
import statistics

from honbicka.modely import Hrana, Koncept, Mapa, Pravdivost, Profil, TypUzlu, Uzel, Zadani
from honbicka.orchestrator import LosovaneParametry
from honbicka.validatory.simulace import (
    POCET_SIMULACI_DEFAULT,
    ocekavana_pozice_aha,
    pasmo_aha,
    povinne_uzly,
    simuluj,
)
from honbicka.validatory.skalovani import komponenty_rozsah

AHA_UZEL_DEFAULT = 10  # postava mezi uzlem 7 a uzlem 8 (~70 % trunku)


def _regiony(zadani: Zadani) -> tuple[str, str]:
    prost = [p for p in (zadani.prostredi or []) if p] or ["les"]
    reg_a = prost[0]
    reg_b = prost[1] if len(prost) > 1 else ("potok" if reg_a != "potok" else "louka")
    return reg_a, reg_b


# Počet simulačních průchodů (spec „≥5"). 15 dává stabilní medián pozice AHA
# (5 průchodů je pro výběr uzlu příliš šumivé). V4: alias na jediný zdroj
# (validatory.simulace), ať se scaffolder a vyrob_hru validace neliší počtem
# průchodů (dřív způsobilo bug — jiný medián podle toho, které volání se použilo).
POCET_SIMULACI = POCET_SIMULACI_DEFAULT


def _pozice_aha(mapa: Mapa, zadani: Zadani, profil: int, uzel: int) -> float | None:
    """Pozice AHA (v čase, %) pro daný kandidátní uzel — analyticky (absorbující
    Markovův řetězec, deterministické a hladké). Fallback na mediánovou simulaci,
    kdyby analytika vrátila None (uzel není dominátor / degenerovaný graf)."""
    analyticka = ocekavana_pozice_aha(mapa, zadani, profil, uzel)
    if analyticka is not None:
        return analyticka
    mapa_kopie_aha = mapa.pozice_aha_uzel
    mapa.pozice_aha_uzel = uzel
    pcts = [r.pozice_aha_pct for r in simuluj(mapa, zadani, profil, pocet=POCET_SIMULACI)
            if r.pozice_aha_pct >= 0]
    mapa.pozice_aha_uzel = mapa_kopie_aha
    return statistics.median(pcts) if pcts else None


def _vyber_aha_uzel(mapa: Mapa, zadani: Zadani) -> int:
    """Vybere uzel na povinné trase, jehož ANALYTICKÁ pozice AHA (v čase) je
    nejblíž STŘEDU pásma pro 60min i 30min zároveň — nejbezpečnější vůči
    okrajům pásma. Deterministické (žádná simulační variabilita — #5)."""
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
        m60 = _pozice_aha(mapa, zadani, 60, d)
        m30 = _pozice_aha(core, zadani, 30, d)
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
    # Uzly 7/10 jsou POSTAVA místo generického rozcestí/přechodu (SC1/V1):
    # typové minima (větve/smyčky/slepé/jednosměrky) se počítají z hran a
    # jiných typů, ne z těchto dvou, takže retyp je bezpečný a dodá CORE
    # potřebné 3 postavy (§SKÁLOVÁNÍ „Postavy" 30min = 3–4).
    add(1, T.ONBOARDING, reg_a, [2], C)
    add(2, T.ROZCESTI, reg_a, [3, 4, 13], C, kostka=True)   # 13 = jediný vstup do SIDE
    add(3, T.INFORMACE, reg_a, [5], C)
    add(4, T.INFORMACE, reg_a, [5], C)
    add(5, T.STREZ, reg_a, [6], C, kostka=True)
    add(6, T.GATED, reg_a, [7], C, komp_=[komp[0]])
    add(7, T.POSTAVA, reg_a, [10, 9], C, kostka=True)       # postava: volba trunk(10)/slepá(9)
    add(8, T.POSTAVA, reg_a, [11], C, komp_=[komp[1]])      # postava (za AHA uzlem)
    add(9, T.SLEPA, reg_a, [7], C)
    add(10, T.POSTAVA, reg_a, [8], C)                       # postava = dominátor mezi 7 a 8 (~AHA)
    add(11, T.SMYCKA, reg_a, [12], C, kostka=True)
    add(12, T.CIL, reg_a, [], C)
    # --- SIDE region B (jen 60min), sbíhá se do uzlu 7 před AHA ---------- #
    # Uzel 13 = léčitel (engine: stavy „vždy léčitelné", herní list na něj
    # odkazuje — v mapě dřív chyběl). Uzel 14 = postava (dřív generický sběr).
    # Spolu s CORE (7,8,10) dávají 60min postavy=4+lecitel=1=5 (§SKÁLOVÁNÍ 5–7).
        # --- SIDE region B (jen 60min), sbíhá se do uzlu 7 před AHA ---------- #
    LAYOUTS = [
        # Layout 1: Split & Merge (13->14/16, merges at 19, loopback 19->14)
        {
            13: [14, 16], 15: [14],
            14: [17, 15], 16: [18],
            17: [19], 18: [19],
            19: [20, 14], 20: [21], 21: [7]
        },
        # Layout 2: Loop / Stuck (14->16->17->14 loop, escape via 16->18, loopback 20->16)
        {
            13: [14, 15], 15: [13],
            14: [16], 16: [17, 18],
            17: [14], 18: [19],
            19: [20], 20: [21, 16], 21: [7]
        },
        # Layout 3: Double Branching (13->14/16, 16->18/20)
        {
            13: [14, 16], 15: [14],
            14: [17, 15], 16: [18, 20],
            17: [19], 18: [19],
            19: [21], 20: [21], 21: [7]
        },
        # Layout 4: Web (Split at 14, merge/split at 18/19, loopback 20->14)
        {
            13: [14, 15], 15: [13],
            14: [16, 17], 16: [18],
            17: [19], 18: [20],
            19: [20], 20: [21, 14], 21: [7]
        },
        # Layout 5: High Risk Shortcut (Short path 13->16->18->21, long loop 13->14->17->19->20->21)
        {
            13: [14, 16], 15: [14],
            14: [17, 15], 16: [18],
            17: [19], 18: [21],
            19: [20], 20: [21], 21: [7]
        },
        # Layout 6: Circular Maze (Looping back to 13 from 17, loopback 19->16)
        {
            13: [14, 15], 15: [13],
            14: [16], 16: [17, 18],
            17: [13], 18: [19],
            19: [20, 16], 20: [21], 21: [7]
        },
        # Layout 7: Central Hub (19 is a central hub, loopback 19->14)
        {
            13: [14, 16], 15: [13],
            14: [17, 15], 16: [18],
            17: [19], 18: [19],
            19: [20, 14], 20: [21], 21: [7]
        },
        # Layout 8: Multiple loops and forks (loopback 18->14)
        {
            13: [14, 16], 15: [14],
            14: [15, 17], 16: [18],
            17: [19], 18: [20, 14],
            19: [16],
            20: [21], 21: [7]
        },
        # Layout 9: Decoy / Fork (13->18 gated, 13->14 postava, loopback 19->14)
        {
            13: [14, 18], 15: [14],
            14: [16, 15], 16: [17],
            17: [19], 18: [19],
            19: [20, 14], 20: [21], 21: [7]
        },
        # Layout 10: Loop back from JEDNOSMER (21->14)
        {
            13: [14, 15], 15: [13],
            14: [16], 16: [17, 18],
            17: [19], 18: [20],
            19: [21], 20: [21],
            21: [7, 14]
        }
    ]

    layout_idx = params.seed % len(LAYOUTS)
    lay = LAYOUTS[layout_idx]

    add(13, T.LECITEL, reg_b, lay[13], S)
    add(14, T.POSTAVA, reg_b, lay[14], S, kostka=True)
    add(15, T.SLEPA, reg_b, lay[15], S)
    add(16, T.STREZ, reg_b, lay[16], S, komp_=([komp[2]] if komp_min > 2 else None))
    add(17, T.INFORMACE, reg_b, lay[17], S, kostka=True)
    add(18, T.GATED, reg_b, lay[18], S, komp_=([komp[3]] if komp_min > 3 else None))
    add(19, T.OBCHODNIK, reg_b, lay[19], S)
    add(20, T.SMYCKA, reg_b, lay[20], S)
    add(21, T.JEDNOSMER, reg_b, lay[21], S)

    # MD2: přiřaď pravdivostní hodnotu INFORMACE uzlům dle koncept-počtu
    # pravdivých stop (SKILL.md §INFORMACE JSOU ODMĚNA) — dřív šlo jen o číslo
    # v konceptu bez opory v mapě, teď R1/R2 mají co ověřovat. Pevná kostra má
    # jen 2 (CORE) / 3 (CORE+SIDE) INFORMACE uzly; když `pravdive_stopy` sahá na
    # (nebo přes) tenhle počet, všechny vyjdou jako PRAVDA a nezbyde místo na
    # zavádějící/lež — známé zjednodušení pevné topologie (viz docs/rozhodnuti.md).
    informacni = sorted((u for u in uzly if u.typ == T.INFORMACE), key=lambda u: u.cislo)
    zbyva_pravda = koncept.pravdive_stopy
    for i, u in enumerate(informacni):
        if zbyva_pravda > 0:
            u.pravdivost = Pravdivost.PRAVDA
            zbyva_pravda -= 1
        else:
            u.pravdivost = Pravdivost.LEZ if i % 2 == 0 else Pravdivost.ZAVADEJICI

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
