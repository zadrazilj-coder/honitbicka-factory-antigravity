"""WeasyPrint sazba: karty (30/60), herní listy, průvodce, kalibrační arch.

Známé pasti WeasyPrint (spec §6) jako konstanty + testy:
- `body { margin: 0 }`;
- karty pozicované absolutně na archu (flex/grid kontejnery WeasyPrint láme
  přes stránky);
- `write_pdf(..., full_fonts=True)` (fontTools subsetting padá na emoji);
- DejaVu Sans kvůli češtině;
- emoji nahradit textovými symboly ▶ ✓ ✗ ◆.
"""

# Textové symboly místo emoji (spec §6) — tisk nezávisí na barevných fontech.
SYM_VOLBA = "▶"  # ▶
SYM_ANO = "✓"  # ✓
SYM_NE = "✗"  # ✗
SYM_KOSTKA = "◆"  # ◆

__all__ = ["SYM_VOLBA", "SYM_ANO", "SYM_NE", "SYM_KOSTKA"]
