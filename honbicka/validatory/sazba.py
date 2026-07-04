"""A5 fit-check reálným renderem (spec §6, ne odhad znaků).

Každá strana karty se vyrenderuje do boxu šíře A5 (`height: auto`); ze skutečné
výšky obsahu (WeasyPrint) se porovná s využitelnou výškou A5 mínus rezerva 4 %.
Odhad podle počtu znaků NESTAČÍ — rozhoduje render.

`measurer` je injektovatelný: default používá WeasyPrint (vyžaduje GTK; jinak
`SazbaNedostupna`), testy dodají fake. Nikdy „skoro projde" — bez čistého
fit-checku se netiskne (spec §12).
"""

from __future__ import annotations

from collections.abc import Callable

from honbicka.modely import FitCheck, Karta
from honbicka.sazba.karta_html import karta_strana_html
from honbicka.sazba.render import SazbaNedostupna, _zajisti_gtk_dll_cestu

# A5 na výšku, mm (dodatek 3.4-7).
A5_SIRKA_MM = 148.0
A5_VYSKA_MM = 210.0
REZERVA = 0.04  # 4 % (spec §6)

# Rozvržení karty (okraje/hlavička/patička) — sladěno s M5 sazbou.
OKRAJ_MM = 10.0
HLAVICKA_MM = 12.0
PATICKA_MM = 8.0

# Měřič: (html_fragment, šířka_mm) → výška obsahu v mm.
Measurer = Callable[[str, float], float]

__all__ = [
    "SazbaNedostupna", "Measurer", "fit_check_karty", "fit_check_strany",
    "limit_mm", "sirka_obsahu_mm", "vyuzitelna_vyska_mm",
]


def sirka_obsahu_mm() -> float:
    return A5_SIRKA_MM - 2 * OKRAJ_MM


def vyuzitelna_vyska_mm() -> float:
    return A5_VYSKA_MM - 2 * OKRAJ_MM - HLAVICKA_MM - PATICKA_MM


def limit_mm() -> float:
    """Využitelná výška mínus rezerva 4 %."""
    return round(vyuzitelna_vyska_mm() * (1 - REZERVA), 1)


def _weasy_measurer(html_fragment: str, sirka_mm: float) -> float:
    """Reálný render fragmentu do boxu dané šíře; vrátí výšku obsahu v mm."""
    _zajisti_gtk_dll_cestu()
    try:
        from weasyprint import CSS, HTML
    except Exception as exc:  # native GTK libs chybí
        raise SazbaNedostupna(
            "WeasyPrint/GTK není dostupné — reálný A5 fit-check nelze provést. "
            "Nainstaluj GTK runtime (viz README) nebo dodej vlastní measurer."
        ) from exc

    dokument = (
        f"<html><body><div class='karta'>{html_fragment}</div></body></html>"
    )
    css = CSS(string=(
        f"@page {{ size: {sirka_mm}mm 4000mm; margin: 0 }} "
        "body { margin: 0; font-family: 'DejaVu Sans'; font-size: 10pt } "
        f".karta {{ width: {sirka_mm}mm }}"
    ))
    doc = HTML(string=dokument).render(stylesheets=[css])
    page = doc.pages[0]
    body = page._page_box.children[0]
    vyska_px = body.height  # CSS px (96 px/palec)
    return vyska_px / 96.0 * 25.4


def fit_check_strany(cislo: int, strana: str, html_fragment: str, measurer: Measurer) -> FitCheck:
    vyska = measurer(html_fragment, sirka_obsahu_mm())
    lim = limit_mm()
    return FitCheck(
        karta=cislo, strana=strana, vyska_mm=round(vyska, 1), limit_mm=lim,
        verdikt=vyska <= lim,
    )


def fit_check_karty(karta: Karta, *, measurer: Measurer | None = None) -> list[FitCheck]:
    """Fit-check všech neprázdných stran karty (přední, zadní, případně zadní_30)."""
    m = measurer or _weasy_measurer
    vysledky: list[FitCheck] = []
    for strana in ("predni", "zadni", "zadni_30"):
        if strana == "zadni_30" and karta.zadni_30 is None:
            continue
        html = karta_strana_html(karta, strana)
        vysledky.append(fit_check_strany(karta.cislo, strana, html, m))
    return vysledky
