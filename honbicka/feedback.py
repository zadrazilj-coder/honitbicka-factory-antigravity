"""Feedback smyčka (spec §7): šablona playtestu a čtení vyplněných výsledků
zpět do téma-generátoru a architekta."""

from __future__ import annotations

import os

from honbicka.sazba.pruvodce import FEEDBACK_OTAZKY

_SABLONA_MARKER = "<!-- VYPLŇ ODPOVĚDI NÍŽE -->"


def sablona_text(slug: str) -> str:
    otazky = "\n\n".join(f"## {o}\n\n> " for o in FEEDBACK_OTAZKY)
    return f"# Playtest — {slug}\n\n{_SABLONA_MARKER}\n\n{otazky}\n"


def zapis_sablonu(slug: str, skiny_dir: str = "skiny") -> str:
    """Vytvoří (nepřepíše) šablonu `skiny/<slug>/playtest_vysledky.md`. Vrátí cestu."""
    hra_dir = os.path.join(skiny_dir, slug)
    os.makedirs(hra_dir, exist_ok=True)
    cesta = os.path.join(hra_dir, "playtest_vysledky.md")
    if not os.path.exists(cesta):
        with open(cesta, "w", encoding="utf-8") as f:
            f.write(sablona_text(slug))
    return cesta


def _je_vyplneny(text: str) -> bool:
    """Heuristika: za značkou „> " je nějaká odpověď (ne jen prázdná šablona)."""
    for radek in text.splitlines():
        r = radek.strip()
        if r.startswith(">") and r.lstrip(">").strip():
            return True
    return False


def nacti_feedbacky(skiny_dir: str = "skiny", limit: int = 10) -> list[str]:
    """Načte vyplněné playtesty (nejnovější první, max `limit`) jako texty."""
    if not os.path.isdir(skiny_dir):
        return []
    nalezene: list[tuple[float, str]] = []
    for slug in os.listdir(skiny_dir):
        cesta = os.path.join(skiny_dir, slug, "playtest_vysledky.md")
        if not os.path.isfile(cesta):
            continue
        with open(cesta, encoding="utf-8") as f:
            text = f.read()
        if _je_vyplneny(text):
            nalezene.append((os.path.getmtime(cesta), text.strip()))
    nalezene.sort(key=lambda t: t[0], reverse=True)
    return [text for _, text in nalezene[:limit]]
