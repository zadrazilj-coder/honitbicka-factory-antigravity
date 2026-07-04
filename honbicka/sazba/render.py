"""Sdílený WeasyPrint render (spec §6). Guardovaný — bez GTK vyhodí SazbaNedostupna.

Pasti WeasyPrint (spec §6): `body{margin:0}`, karty absolutně pozicované na archu
(ne flex/grid — WeasyPrint je láme přes stránky), `write_pdf(full_fonts=True)`
(fontTools subsetting padá na emoji), DejaVu Sans kvůli češtině.
"""

from __future__ import annotations


class SazbaNedostupna(RuntimeError):
    """WeasyPrint/GTK není k dispozici → nelze renderovat/měřit PDF."""


def je_dostupne() -> bool:
    """True, když WeasyPrint včetně native GTK knihoven naběhne."""
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


def zapis_pdf(html: str, cesta: str, *, base_url: str | None = None) -> None:
    """Vyrenderuje HTML do PDF na `cesta`. `full_fonts=True` (spec §6).

    Bez GTK vyhodí `SazbaNedostupna` — nikdy netiskne „naslepo" (spec §12).
    """
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise SazbaNedostupna(
            "WeasyPrint/GTK není dostupné — PDF nelze vyrenderovat. "
            "Nainstaluj GTK runtime (viz README)."
        ) from exc
    HTML(string=html, base_url=base_url).write_pdf(cesta, full_fonts=True)
