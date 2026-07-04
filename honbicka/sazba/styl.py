"""Geometrie a CSS pro sazbu (spec §6). Imposice: portrait karty 148×210,
2 vedle sebe na A4 na šířku, svislý řez (viz docs/rozhodnuti.md)."""

from __future__ import annotations

from honbicka.modely import TypUzlu

# A4 na šířku (mm) = arch se dvěma A5 portrait kartami vedle sebe.
ARCH_SIRKA_MM = 297.0
ARCH_VYSKA_MM = 210.0
SLOT_SIRKA_MM = 148.5  # polovina A4 na šířku
SLOT_VYSKA_MM = 210.0
REZ_X_MM = 148.5  # svislý řez uprostřed

# Barvy typů uzlů (spec §výstup „barevné typy uzlů").
TYP_BARVA: dict[TypUzlu, str] = {
    TypUzlu.ONBOARDING: "#4c8bf5", TypUzlu.ROZCESTI: "#8e7cc3",
    TypUzlu.SBER: "#6aa84f", TypUzlu.PRECHOD: "#93c47d",
    TypUzlu.SLEPA: "#999999", TypUzlu.JEDNOSMER: "#e69138",
    TypUzlu.SMYCKA: "#c27ba0", TypUzlu.STREZ: "#cc0000",
    TypUzlu.GATED: "#a64d79", TypUzlu.INFORMACE: "#3d85c6",
    TypUzlu.POSTAVA: "#f1c232", TypUzlu.LECITEL: "#45818e",
    TypUzlu.OBCHODNIK: "#b45f06", TypUzlu.CIL: "#000000",
}

# Textové symboly místo emoji (spec §6): tisk nezávisí na barevných fontech.
SYM_VOLBA = "▶"  # ▶
SYM_ANO = "✓"    # ✓
SYM_NE = "✗"     # ✗
SYM_KOSTKA = "◆"  # ◆

# Pasti WeasyPrint jako CSS konstanty (spec §6): body margin 0, absolutní
# pozicování archu (NE flex/grid), DejaVu Sans (čeština).
CSS_ARCH_KARTY = f"""
@page {{ size: {ARCH_SIRKA_MM}mm {ARCH_VYSKA_MM}mm; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; }}
.arch {{ position: relative; width: {ARCH_SIRKA_MM}mm; height: {ARCH_VYSKA_MM}mm;
        page-break-after: always; overflow: hidden; }}
.slot {{ position: absolute; top: 0; width: {SLOT_SIRKA_MM}mm; height: {SLOT_VYSKA_MM}mm;
        padding: 8mm 10mm; }}
.slot-left {{ left: 0; }}
.slot-right {{ left: {REZ_X_MM}mm; }}
.rez {{ position: absolute; top: 0; left: {REZ_X_MM}mm; height: {ARCH_VYSKA_MM}mm;
        border-left: 0.2mm dashed #000; }}
.hlavicka {{ border-bottom: 1mm solid; padding-bottom: 2mm; margin-bottom: 3mm;
            font-weight: bold; }}
.atmosfera {{ font-style: italic; }}
"""

CSS_A5_LIST = """
@page { size: 148mm 210mm; margin: 10mm; }
body { margin: 0; font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; }
.pocitadlo span { display: inline-block; width: 6mm; height: 6mm;
    border: 0.2mm solid #000; margin: 0.5mm; text-align: center; }
.slot-inv { display: inline-block; width: 100%; border-bottom: 0.2mm dashed #000;
    height: 7mm; }
"""

CSS_A4_PRUVODCE = """
@page { size: 210mm 297mm; margin: 18mm; }
body { margin: 0; font-family: 'DejaVu Sans', sans-serif; font-size: 11pt; line-height: 1.4; }
h1 { font-size: 18pt; } h2 { font-size: 14pt; border-bottom: 0.3mm solid #000; }
.spoiler { background: #f3f3f3; padding: 4mm; }
.epilog { border: 0.4mm solid #000; padding: 4mm; }
"""
