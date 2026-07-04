"""Deterministické validátory (spec §3: LLM tvoří, Python rozhoduje).

ŽÁDNÝ validátor nesmí volat LLM. Vše se ověřuje algoritmicky nad daty mapy
a nad reálným renderem sazby.
"""

from dataclasses import dataclass, field


@dataclass
class VysledekValidace:
    """Jednotný výsledek deterministické kontroly."""

    ok: bool = True
    chyby: list[str] = field(default_factory=list)
    # Diagnostiky pro cílený opravný prompt architektovi (spec §4 FÁZE 1/2).
    diagnostika: list[str] = field(default_factory=list)

    def selhani(self, zprava: str, diagnoza: str | None = None) -> None:
        self.ok = False
        self.chyby.append(zprava)
        if diagnoza:
            self.diagnostika.append(diagnoza)


__all__ = ["VysledekValidace"]
