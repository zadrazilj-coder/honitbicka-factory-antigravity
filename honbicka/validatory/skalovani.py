"""Škálovací počty dle profilu délky × věk (SKILL.md §SKÁLOVÁNÍ, Patro 1 body 5 a 9).

Factory používá jen profily 30 a 60 (docs/rozhodnuti.md). Kontrolují se počty
odvoditelné z grafu mapy (typy uzlů, komponenty, kostka %, práh počítadla).
Koncept-úrovňové počty (falešné teorie, pravdivé stopy, konce) se předávají
volitelně — naplní je M3 z konceptu; bez nich se přeskočí (viz docstring dole).
"""

from __future__ import annotations

from dataclasses import dataclass

from honbicka.modely import Mapa, Obtiznost, TypUzlu, VekPasmo, Zadani
from honbicka.validatory import VysledekValidace

# Věková pásma (factory) s tvrdým stropem: max 1 falešná teorie a 2 konce
# bez ohledu na délku (SKILL.md §SKÁLOVÁNÍ „Věkový strop").
VEK_STROP: set[VekPasmo] = {VekPasmo.V04_06, VekPasmo.V06_09}

# Podíl karet s kostkou (~30 %, SKILL.md §KOSTKA) s tolerancí.
KOSTKA_PODIL_MIN = 0.20
KOSTKA_PODIL_MAX = 0.45


@dataclass(frozen=True)
class SkalaProfilu:
    karty: tuple[int, int]
    strezene: tuple[int, int]
    gated: tuple[int, int]
    informacni_min: int
    regiony: tuple[int, int]
    obchodnik_povinny: bool
    inventar: int
    falesne_teorie: tuple[int, int]
    pravdive_stopy_min: int
    konce: tuple[int, int]


# Tabulka §SKÁLOVÁNÍ pro 30 a 60 min.
SKALA: dict[int, SkalaProfilu] = {
    30: SkalaProfilu(
        karty=(8, 12), strezene=(1, 2), gated=(1, 1), informacni_min=2,
        regiony=(1, 2), obchodnik_povinny=False, inventar=3,
        falesne_teorie=(1, 1), pravdive_stopy_min=2, konce=(2, 2),
    ),
    60: SkalaProfilu(
        karty=(18, 25), strezene=(2, 3), gated=(2, 2), informacni_min=3,
        regiony=(2, 3), obchodnik_povinny=True, inventar=5,
        falesne_teorie=(2, 2), pravdive_stopy_min=3, konce=(2, 3),
    ),
}


def komponenty_rozsah(profil_min: int, obtiznost: Obtiznost) -> tuple[int, int]:
    """Počet komponent artefaktu (SKILL.md §P4). U 30min vždy 2."""
    if profil_min == 30:
        return (2, 2)
    return {
        Obtiznost.LEHKA: (2, 3),
        Obtiznost.STREDNI: (3, 4),
        Obtiznost.TEZKA: (4, 5),
    }[obtiznost]


def _v_rozsahu(hodnota: int, rozsah: tuple[int, int]) -> bool:
    return rozsah[0] <= hodnota <= rozsah[1]


def zkontroluj_skalovani(
    mapa: Mapa,
    zadani: Zadani,
    profil_min: int,
    *,
    falesne_teorie: int | None = None,
    pravdive_stopy: int | None = None,
    konce: int | None = None,
) -> VysledekValidace:
    """Ověří počty dané profilem. Pro 30min předej CORE podgraf (spec §5).

    Koncept-úrovňové počty (`falesne_teorie`, `pravdive_stopy`, `konce`) jsou
    volitelné; když jsou None, kontrola se pro ně přeskočí (naplní M3).
    """
    v = VysledekValidace()
    if profil_min not in SKALA:
        v.selhani(f"neznámý profil {profil_min} (factory používá 30/60)")
        return v
    s = SKALA[profil_min]

    pocet_karet = len(mapa.uzly)
    if not _v_rozsahu(pocet_karet, s.karty):
        v.selhani(f"počet karet {pocet_karet} mimo {s.karty} pro {profil_min}min")

    def typ(t: TypUzlu) -> int:
        return sum(1 for u in mapa.uzly if u.typ == t)

    strezene = typ(TypUzlu.STREZ)
    if not _v_rozsahu(strezene, s.strezene):
        v.selhani(f"střežené lokace {strezene} mimo {s.strezene}")

    gated = typ(TypUzlu.GATED)
    if not _v_rozsahu(gated, s.gated):
        v.selhani(f"gated lokace {gated} mimo {s.gated}")

    informacni = typ(TypUzlu.INFORMACE)
    if informacni < s.informacni_min:
        v.selhani(f"informačních uzlů {informacni} < {s.informacni_min}")

    regiony = len({u.region for u in mapa.uzly})
    if not _v_rozsahu(regiony, s.regiony):
        v.selhani(f"regionů {regiony} mimo {s.regiony}")

    obchodnik = typ(TypUzlu.OBCHODNIK)
    if s.obchodnik_povinny and obchodnik < 1:
        v.selhani(f"chybí obchodník (povinný u {profil_min}min)")

    # Komponenty artefaktu (distinct napříč uzly).
    komp_rozsah = komponenty_rozsah(profil_min, zadani.obtiznost)
    komponenty = len({k for u in mapa.uzly for k in u.komponenty})
    if not _v_rozsahu(komponenty, komp_rozsah):
        v.selhani(f"komponent artefaktu {komponenty} mimo {komp_rozsah}")

    # Kostka ~30 % karet.
    s_kostkou = sum(1 for u in mapa.uzly if u.kostka)
    podil = s_kostkou / pocet_karet if pocet_karet else 0.0
    if not (KOSTKA_PODIL_MIN <= podil <= KOSTKA_PODIL_MAX):
        v.selhani(f"podíl karet s kostkou {podil:.0%} mimo 20–45 %")

    # Práh počítadla: násobek 5 v 80–120 (dodatek 3.4-1).
    prah = mapa.prah_aktivity
    if prah % 5 != 0 or not (80 <= prah <= 120):
        v.selhani(f"práh počítadla {prah} musí být násobek 5 v 80–120 (3.4-1)")

    # Koncept-úrovňové počty + věkový strop.
    strop = zadani.vek in VEK_STROP
    if falesne_teorie is not None:
        max_teorie = 1 if strop else s.falesne_teorie[1]
        min_teorie = min(s.falesne_teorie[0], max_teorie)
        if not (min_teorie <= falesne_teorie <= max_teorie):
            v.selhani(
                f"falešných teorií {falesne_teorie} mimo [{min_teorie},{max_teorie}]"
                + (" (věkový strop)" if strop else "")
            )
    if pravdive_stopy is not None and pravdive_stopy < s.pravdive_stopy_min:
        v.selhani(f"pravdivých stop {pravdive_stopy} < {s.pravdive_stopy_min}")
    if konce is not None:
        max_konce = 2 if strop else s.konce[1]
        if not (s.konce[0] <= konce <= max_konce):
            v.selhani(
                f"konců {konce} mimo [{s.konce[0]},{max_konce}]"
                + (" (věkový strop)" if strop else "")
            )

    return v
