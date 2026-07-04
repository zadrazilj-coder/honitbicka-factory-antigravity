"""BFS/náhodná simulace průchodů (SKILL.md §VALIDACE Patro 1 bod 12).

≥5 náhodných průchodů: délka (2,5 min/kartu venku, 1,5–2 uvnitř), pozice AHA
v ČASE v pásmu dle archetypu a formátu (dodatek 3.4-2), pravidlo první návštěvy
u volného formátu (3.4-3), klíčové svědectví na povinné trase (3.4-4).
Deterministické (seed). ŽÁDNÝ LLM.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter, deque

from honbicka.modely import Archetyp, Mapa, SimulaceReport, TypUzlu, Zadani
from honbicka.validatory import VysledekValidace
from honbicka.validatory.topologie import _start_uzel

# Tempo (min/kartu) dle prostředí uzlu (SKILL.md §SKÁLOVÁNÍ Odhad tempa).
TEMPO_VENKU = 2.5
TEMPO_UVNITR = 1.75  # střed 1,5–2
PROSTREDI_UVNITR = {"byt", "hotel"}

# Pravidlo první návštěvy (3.4-3): opakovaný průchod ~40 % tempa.
TEMPO_OPAKOVANI = 0.4

# Tolerance délky vůči profilu (min). Délka se odhaduje z počtu karet
# (2,5 min/kartu venku — SKILL.md §SKÁLOVÁNÍ „Odhad tempa"), NE z nejrychlejšího
# průchodu: 60min „master" sdílí CORE s 30min hrou, takže beeline je krátký;
# délku profilu nese počet karet a jejich průzkum (viz docs/rozhodnuti.md).
DELKA_PASMO = {30: (18.0, 48.0), 60: (36.0, 96.0)}


def odhad_delky_min(mapa: Mapa) -> float:
    """Odhad délky hry = součet tempa přes všechny karty (první návštěva)."""
    return round(sum(_tempo_uzlu(u.prostredi) for u in mapa.uzly), 1)


def pasmo_aha(archetyp: Archetyp, je_volny_format: bool) -> tuple[float, float]:
    """Pásmo pozice AHA v % (dodatek 3.4-2).

    A2 = 68–85 %; ostatní (A1,A3,A4,A5,A6,A7) = 65–80 % (default dle
    docs/rozhodnuti.md). Volný formát: horní mez +7 p. b.
    """
    if archetyp == Archetyp.A2:
        low, high = 68.0, 85.0
    else:
        low, high = 65.0, 80.0
    if je_volny_format:
        high += 7.0
    return low, high


def _tempo_uzlu(prostredi: str) -> float:
    return TEMPO_UVNITR if prostredi.lower() in PROSTREDI_UVNITR else TEMPO_VENKU


def _vzdalenost_do_cile(mapa: Mapa) -> dict[int, int]:
    """Počet hran nejkratší cestou do nejbližšího `cil` (reverzní BFS)."""
    cile = {u.cislo for u in mapa.uzly if u.typ == TypUzlu.CIL}
    rev: dict[int, list[int]] = {u.cislo: [] for u in mapa.uzly}
    for u in mapa.uzly:
        for h in u.hrany:
            if h.cil in rev:
                rev[h.cil].append(u.cislo)
    dist: dict[int, int] = {c: 0 for c in cile}
    fronta = deque(cile)
    while fronta:
        n = fronta.popleft()
        for p in rev.get(n, []):
            if p not in dist:
                dist[p] = dist[n] + 1
                fronta.append(p)
    return dist


def povinne_uzly(mapa: Mapa) -> set[int]:
    """Uzly, kterými MUSÍ projít každá cesta start→cíl (dominátory cíle).

    Uzel je povinný, když jeho odebráním přestane být cíl dosažitelný ze startu.
    """
    start = _start_uzel(mapa)
    if start is None:
        return set()
    cile = {u.cislo for u in mapa.uzly if u.typ == TypUzlu.CIL}
    if not cile:
        return set()

    def dosahne_cil_bez(vynech: int) -> bool:
        graf = {u.cislo: [h.cil for h in u.hrany] for u in mapa.uzly}
        vid: set[int] = set()
        fronta = deque([start.cislo])
        while fronta:
            n = fronta.popleft()
            if n in vid or n == vynech:
                continue
            vid.add(n)
            if n in cile:
                return True
            for c in graf.get(n, []):
                if c not in vid and c != vynech:
                    fronta.append(c)
        return False

    povinne: set[int] = set()
    for u in mapa.uzly:
        if u.cislo == start.cislo or u.typ == TypUzlu.CIL:
            continue
        if not dosahne_cil_bez(u.cislo):
            povinne.add(u.cislo)
    return povinne


def _jeden_pruchod(mapa: Mapa, rng: random.Random, volny_format: bool) -> SimulaceReport | None:
    start = _start_uzel(mapa)
    dist = _vzdalenost_do_cile(mapa)
    if start is None or start.cislo not in dist:
        return None  # start nedosáhne cíle → topologie to zachytí

    node = start.cislo
    navstivy: Counter[int] = Counter()
    cas = 0.0
    aha_cas: float | None = None
    max_kroku = len(mapa.uzly) * 6

    for _ in range(max_kroku + 1):
        u = mapa.uzel(node)
        assert u is not None
        prvni = navstivy[node] == 0
        navstivy[node] += 1
        tempo = _tempo_uzlu(u.prostredi)
        if volny_format and not prvni:
            tempo *= TEMPO_OPAKOVANI
        cas += tempo
        if node == mapa.pozice_aha_uzel and aha_cas is None:
            aha_cas = cas
        if u.typ == TypUzlu.CIL:
            pct = (aha_cas / cas * 100.0) if aha_cas is not None else None
            return SimulaceReport(
                profil="", delka_min=round(cas, 2),
                pozice_aha_pct=round(pct, 1) if pct is not None else -1.0,
                aha_v_pasmu=False, dosahl_cile=True,
            )
        # kandidátní hrany, jejichž cíl ještě umí dosáhnout cíle
        kand = [h for h in u.hrany if h.cil in dist]
        if not kand:
            return SimulaceReport(profil="", delka_min=round(cas, 2),
                                  pozice_aha_pct=-1.0, aha_v_pasmu=False, dosahl_cile=False)
        # postupové hrany (snižují vzdálenost) mají vyšší váhu → hra dojde
        vahy = [2 if dist[h.cil] < dist[node] else 1 for h in kand]
        node = rng.choices([h.cil for h in kand], weights=vahy, k=1)[0]

    return SimulaceReport(profil="", delka_min=round(cas, 2),
                          pozice_aha_pct=-1.0, aha_v_pasmu=False, dosahl_cile=False)


def simuluj(
    mapa: Mapa, zadani: Zadani, profil_min: int, pocet: int = 5, seed: int | None = None
) -> list[SimulaceReport]:
    """≥5 průchodů. Pro 30min předej CORE podgraf (spec §5).

    Seed default = mapa.seed → reprodukovatelnost (spec §3)."""
    rng = random.Random(seed if seed is not None else mapa.seed)
    low, high = pasmo_aha(mapa.archetyp, zadani.je_volny_format)
    reporty: list[SimulaceReport] = []
    for _ in range(max(5, pocet)):
        r = _jeden_pruchod(mapa, rng, zadani.je_volny_format)
        if r is None:
            reporty.append(SimulaceReport(
                profil=str(profil_min), delka_min=0.0, pozice_aha_pct=-1.0,
                aha_v_pasmu=False, dosahl_cile=False))
            continue
        r.profil = str(profil_min)
        r.aha_v_pasmu = r.pozice_aha_pct >= 0 and low <= r.pozice_aha_pct <= high
        reporty.append(r)
    return reporty


def zkontroluj_simulaci(
    mapa: Mapa, zadani: Zadani, profil_min: int, reporty: list[SimulaceReport]
) -> VysledekValidace:
    """Medián délky v pásmu profilu; medián pozice AHA v pásmu; klíčová
    svědectví na povinné trase (3.4-4); AHA uzel na povinné trase."""
    v = VysledekValidace()
    if not reporty:
        v.selhani("žádná simulace neproběhla")
        return v

    if not all(r.dosahl_cile for r in reporty):
        v.selhani("některý průchod nedosáhl cíle", "zkontroluj dosažitelnost/softlock")

    # Délka profilu se odhaduje z počtu karet (2,5 min/kartu), ne z beeline.
    odhad = odhad_delky_min(mapa)
    pasmo = DELKA_PASMO.get(profil_min)
    if pasmo and not (pasmo[0] <= odhad <= pasmo[1]):
        v.selhani(
            f"odhad délky {odhad:.0f} min mimo {pasmo} pro {profil_min}min",
            f"uber/přidej karty (odhad {odhad:.0f} min, ~2,5 min/kartu)",
        )

    pcts = [r.pozice_aha_pct for r in reporty if r.dosahl_cile and r.pozice_aha_pct >= 0]
    low, high = pasmo_aha(mapa.archetyp, zadani.je_volny_format)
    if not pcts:
        v.selhani(
            "AHA odhalení nebylo v žádném průchodu dosaženo",
            f"přesuň klíčové odhalení (uzel {mapa.pozice_aha_uzel}) na povinnou trasu",
        )
    else:
        med_aha = statistics.median(pcts)
        if not (low <= med_aha <= high):
            v.selhani(
                f"pozice AHA {med_aha:.0f} % mimo pásmo {low:.0f}–{high:.0f} %",
                f"AHA v {med_aha:.0f} %, posuň klíčové svědectví do pásma {low:.0f}–{high:.0f} %",
            )

    # 3.4-4: klíčová svědectví na povinné trase; AHA uzel povinný.
    povinne = povinne_uzly(mapa)
    for u in mapa.uzly:
        if u.klicove_svedectvi and u.cislo not in povinne:
            v.selhani(
                f"klíčové svědectví na uzlu {u.cislo} není na povinné trase (3.4-4)",
                f"pověs uzel {u.cislo} za gated/jednosměrku na povinnou trasu",
            )
    if mapa.pozice_aha_uzel not in povinne:
        v.selhani(
            f"AHA uzel {mapa.pozice_aha_uzel} není na povinné trase",
            f"zajisti, že každá cesta k cíli prochází uzlem {mapa.pozice_aha_uzel}",
        )

    return v
