"""Sdílený WeasyPrint render (spec §6). Guardovaný — bez GTK vyhodí SazbaNedostupna.

Pasti WeasyPrint (spec §6): `body{margin:0}`, karty absolutně pozicované na archu
(ne flex/grid — WeasyPrint je láme přes stránky), `write_pdf(full_fonts=True)`
(fontTools subsetting padá na emoji), DejaVu Sans kvůli češtině.

**Windows DLL past (ověřeno 2026-07-04):** i s nainstalovaným GTK (GTK3/GTK4/MSYS2)
WeasyPrint hlásí `cannot load library 'libgobject-2.0-0'`. Příčina: od Pythonu 3.8
`ctypes`/cffi na Windows IGNORUJE proměnnou `PATH` při hledání závislostí DLL
(bezpečnostní změna — „safe DLL search"); nestačí mít GTK v PATH, je nutné
`os.add_dll_directory()`. `_zajisti_gtk_dll_cestu()` to udělá automaticky, pokud
najde známé umístění (MSYS2 ucrt64/mingw64, GTK3 Runtime, gvsbuild). Jiné umístění
lze nastavit proměnnou prostředí `HONBICKA_GTK_DIR`.
"""

from __future__ import annotations

import os
import sys

# Kandidátní adresáře se sdílenými GTK/Pango knihovnami na Windows (WeasyPrint
# potřebuje jen tyto .dll, ne celý GTK toolkit/GUI). Pořadí = priorita hledání.
_GTK_KANDIDATI_WIN = [
    os.environ.get("HONBICKA_GTK_DIR", ""),
    r"C:\msys64\ucrt64\bin",
    r"C:\msys64\mingw64\bin",
    r"C:\Program Files\GTK3-Runtime Win64\bin",
    r"C:\gtk-build\gtk\x64\release\bin",
]
_GTK_ZNACKOVA_DLL = "libgobject-2.0-0.dll"  # přítomnost = adresář obsahuje GTK libs
_gtk_dll_pripojeno = False


def _zajisti_gtk_dll_cestu(kandidati: list[str] | None = None) -> str | None:
    """Připojí adresář s GTK knihovnami přes `os.add_dll_directory()` (viz past
    výše). Idempotentní (nic neudělá podruhé); no-op mimo Windows nebo na staré
    Python verzi bez `add_dll_directory`. Vrátí připojený adresář, nebo None."""
    global _gtk_dll_pripojeno
    if _gtk_dll_pripojeno or sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return None
    for adresar in (kandidati if kandidati is not None else _GTK_KANDIDATI_WIN):
        if adresar and os.path.isfile(os.path.join(adresar, _GTK_ZNACKOVA_DLL)):
            try:
                os.add_dll_directory(adresar)
            except OSError:
                continue
            _gtk_dll_pripojeno = True
            return adresar
    return None


class SazbaNedostupna(RuntimeError):
    """WeasyPrint/GTK není k dispozici → nelze renderovat/měřit PDF."""


def je_dostupne() -> bool:
    """True, když WeasyPrint včetně native GTK knihoven naběhne."""
    _zajisti_gtk_dll_cestu()
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


def zapis_pdf(html: str, cesta: str, *, base_url: str | None = None) -> None:
    """Vyrenderuje HTML do PDF na `cesta`. `full_fonts=True` (spec §6).

    Bez GTK vyhodí `SazbaNedostupna` — nikdy netiskne „naslepo" (spec §12).
    """
    _zajisti_gtk_dll_cestu()
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise SazbaNedostupna(
            "WeasyPrint/GTK není dostupné — PDF nelze vyrenderovat. "
            "Nainstaluj GTK runtime (viz README)."
        ) from exc
    HTML(string=html, base_url=base_url).write_pdf(cesta, full_fonts=True)
