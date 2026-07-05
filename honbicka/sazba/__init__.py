"""WeasyPrint sazba: karty (30/60), herní listy, průvodce, kalibrační arch.

Známé pasti WeasyPrint (spec §6) jako konstanty + testy:
- `body { margin: 0 }`;
- karty pozicované absolutně na archu (flex/grid kontejnery WeasyPrint láme
  přes stránky);
- `write_pdf(..., full_fonts=True)` (fontTools subsetting padá na emoji);
- DejaVu Sans kvůli češtině;
- emoji nahradit textovými symboly ▶ ✓ ✗ ◆.
"""

# SZ5: symboly žijí v honbicka.sazba.styl (jediný zdroj — tam je odtud
# skutečně importují herni_list.py/karty_pdf.py/pruvodce.py); re-export
# odsud jen pro zpětnou kompatibilitu s `from honbicka.sazba import SYM_*`.
from honbicka.sazba.styl import SYM_ANO, SYM_KOSTKA, SYM_NE, SYM_VOLBA

__all__ = ["SYM_VOLBA", "SYM_ANO", "SYM_NE", "SYM_KOSTKA"]
