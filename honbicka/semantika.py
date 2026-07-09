"""Sémantická okna zákazů registru (doporučení #8).

Registr dnes porovnává mechanismy řešení PŘESNOU shodou řetězců
(`registr.zakazana_okna`), takže „Drak kýchá kvůli pylu" a „Saň má alergii na
květinu" projdou jako dvě různé hry, přestože jde o tentýž nápad. Tady se
mechanismus nového konceptu porovná s posledními hrami přes lokální embeddings
(Ollama `nomic-embed-text`) a kosinovou podobnost.

Zásada „LLM tvoří, Python rozhoduje": embedding je jen numerický podklad;
rozhodnutí (práh podobnosti, re-prompt) dělá Python. Chybí-li embed model nebo
klient `embed()` neumí, funkce MĚKCE degraduje na přesnou shodu — generace hry
kvůli tomu nikdy nespadne (spec §4).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

# Práh kosinové podobnosti, nad kterým považujeme mechanismy za „tentýž nápad".
# 0.82 zvoleno konzervativně: nomic-embed dává parafrázím ~0.85–0.95, tématicky
# příbuzným ale odlišným nápadům ~0.6–0.8 (viz docs/rozhodnuti.md).
PRAH_PODOBNOSTI = 0.82


class _EmbedKlient(Protocol):
    def embed(self, texty: list[str]) -> list[list[float]]: ...


def kosinova_podobnost(a: Sequence[float], b: Sequence[float]) -> float:
    """Kosinová podobnost dvou vektorů; 0.0 pro nulový/neshodný rozměr."""
    if not a or not b or len(a) != len(b):
        return 0.0
    skalar = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return skalar / (na * nb)


def nejpodobnejsi(
    novy: str, stare: Sequence[str], klient: object, *, prah: float = PRAH_PODOBNOSTI
) -> tuple[float, str | None]:
    """Vrátí (max. podobnost, nejpodobnější starý mechanismus) pro `novy`.

    Používá `klient.embed` (jedno dávkové volání pro `novy` + všechny `stare`).
    Když klient `embed` nemá nebo volání selže (chybí embed model, síť),
    MĚKCE degraduje na přesnou shodu: podobnost 1.0 při shodě normalizovaných
    řetězců, jinak 0.0 — tj. přesně dosavadní chování registru, nikdy pád."""
    stare = [s for s in stare if s and s.strip()]
    if not novy.strip() or not stare:
        return 0.0, None
    embed = getattr(klient, "embed", None)
    if callable(embed):
        try:
            vektory = embed([novy, *stare])
            if len(vektory) == len(stare) + 1:
                nv, sv = vektory[0], vektory[1:]
                podobnosti = [(kosinova_podobnost(nv, v), s) for v, s in zip(sv, stare, strict=True)]
                return max(podobnosti, key=lambda t: t[0])
        except Exception:  # noqa: BLE001 — embed nedostupný → degraduj, nespadni
            pass
    # Fallback: přesná shoda (normalizace na malá písmena, ořez).
    n = novy.strip().lower()
    for s in stare:
        if s.strip().lower() == n:
            return 1.0, s
    return 0.0, None


def je_prilis_podobny(
    novy: str, stare: Sequence[str], klient: object, *, prah: float = PRAH_PODOBNOSTI
) -> tuple[bool, float, str | None]:
    """(je_příliš_podobný, max_podobnost, nejpodobnější) — True když ≥ `prah`."""
    skore, ktery = nejpodobnejsi(novy, stare, klient, prah=prah)
    return skore >= prah, skore, ktery
