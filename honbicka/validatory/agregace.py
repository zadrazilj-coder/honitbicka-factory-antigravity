"""Agregace deterministických validátorů (M3).

Spojuje topologii, škálování a simulaci do jednoho verdiktu. Pro pár 30/60
(spec §5) se plný graf validuje jako 60min a CORE podgraf jako 30min.
"""

from __future__ import annotations

from honbicka.modely import Koncept, Mapa, SimulaceReport, Zadani
from honbicka.validatory import VysledekValidace
from honbicka.validatory.simulace import POCET_SIMULACI_DEFAULT, simuluj, zkontroluj_simulaci
from honbicka.validatory.skalovani import zkontroluj_skalovani
from honbicka.validatory.topologie import zkontroluj_topologii


def _sluc(cil: VysledekValidace, zdroj: VysledekValidace, stitek: str = "") -> None:
    if not zdroj.ok:
        cil.ok = False
    predpona = f"[{stitek}] " if stitek else ""
    cil.chyby.extend(predpona + c for c in zdroj.chyby)
    cil.diagnostika.extend(predpona + d for d in zdroj.diagnostika)


def validuj_mapu(
    mapa: Mapa,
    zadani: Zadani,
    profil_min: int,
    koncept: Koncept | None = None,
    *,
    pocet_simulaci: int = POCET_SIMULACI_DEFAULT,
    stitek: str = "",
) -> tuple[VysledekValidace, list[SimulaceReport]]:
    """Topologie + škálování + simulace nad jedním grafem/profilem."""
    v = VysledekValidace()
    _sluc(v, zkontroluj_topologii(mapa), stitek)
    _sluc(
        v,
        zkontroluj_skalovani(
            mapa, zadani, profil_min,
            falesne_teorie=koncept.falesne_teorie if koncept else None,
            pravdive_stopy=koncept.pravdive_stopy if koncept else None,
            konce=koncept.konce if koncept else None,
        ),
        stitek,
    )
    reporty = simuluj(mapa, zadani, profil_min, pocet=pocet_simulaci)
    _sluc(v, zkontroluj_simulaci(mapa, zadani, profil_min, reporty), stitek)
    return v, reporty


def validuj_par_30_60(
    mapa: Mapa, zadani: Zadani, koncept: Koncept | None = None, *,
    pocet_simulaci: int = POCET_SIMULACI_DEFAULT,
) -> tuple[VysledekValidace, dict[str, list[SimulaceReport]]]:
    """Validuje 60min (plný graf) i 30min (CORE podgraf) nezávisle (spec §5).

    Koncept-počty (teorie/stopy/konce) se kontrolují jen proti 60min masteru —
    jeden princip má jeden Koncept popisující 60min; 30min je jeho podmnožina,
    proto se pro CORE koncept-počty přeskočí (viz docs/rozhodnuti.md).
    """
    v = VysledekValidace()
    v60, r60 = validuj_mapu(mapa, zadani, 60, koncept, pocet_simulaci=pocet_simulaci, stitek="60")
    core = mapa.podgraf_core()
    v30, r30 = validuj_mapu(core, zadani, 30, None, pocet_simulaci=pocet_simulaci, stitek="30")
    _sluc(v, v60)
    _sluc(v, v30)
    return v, {"60": r60, "30": r30}
