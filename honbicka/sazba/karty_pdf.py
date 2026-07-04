"""Imposice tiskových karet (spec §6): portrait 148×210, 2 vedle sebe na A4
na šířku, svislý řez; duplex „otáčet po delší straně" → zadní strany ve STEJNÉM
vodorovném pořadí (levá zůstává levá). Kalibrační arch je strana 1–2 každého PDF.
"""

from __future__ import annotations

import html as _html
import math

from honbicka.modely import Karta
from honbicka.sazba.karta_html import karta_strana_html
from honbicka.sazba.render import zapis_pdf
from honbicka.sazba.styl import CSS_ARCH_KARTY, TYP_BARVA


def pocet_stran(pocet_karet: int) -> int:
    """Počet stran PDF = 2 (kalibrace) + 2×⌈N/2⌉ (přední+zadní arch na dvojici)."""
    return 2 + 2 * math.ceil(pocet_karet / 2) if pocet_karet else 2


def _slot(karta: Karta | None, strana: str, poz: str) -> str:
    if karta is None:
        return f"<div class='slot slot-{poz}'></div>"
    barva = TYP_BARVA.get(karta.typ, "#000")
    obsah = karta_strana_html(karta, strana)
    hlavicka = (
        f"<div class='hlavicka' style='border-color:{barva}'>"
        f"#{karta.cislo} {_html.escape(karta.nazev)}"
        f"<span style='float:right;color:{barva}'>{_html.escape(karta.typ.value)}</span></div>"
    )
    return f"<div class='slot slot-{poz}'>{hlavicka}{obsah}</div>"


def _arch(levy: str, pravy: str) -> str:
    return f"<div class='arch'>{levy}{pravy}<div class='rez'></div></div>"


def _kalibrace() -> tuple[str, str]:
    """Přední a zadní kalibrační arch: značka na stejné pozici → při pohledu
    proti světlu se přední/zadní musí krýt (ověření duplexu, spec §6)."""
    znacka = (
        "<div style='position:absolute;left:64mm;top:100mm;width:20mm;height:20mm;"
        "border:0.4mm solid #000'></div>"
    )
    hl_p = "<div class='hlavicka'>KALIBRACE — PŘEDNÍ</div>"
    hl_z = "<div class='hlavicka'>KALIBRACE — ZADNÍ</div>"
    predni = _arch(
        f"<div class='slot slot-left'>{hl_p}"
        f"<p>Vytiskni duplex „otáčet po delší straně“. Přehni arch proti světlu — "
        f"tento rámeček se musí krýt s rámečkem na ZADNÍ straně.</p>{znacka}</div>",
        f"<div class='slot slot-right'>{hl_p}{znacka}</div>",
    )
    zadni = _arch(
        f"<div class='slot slot-left'>{hl_z}"
        f"<p>Zákryt OK → řez i duplex sedí. Zákryt mimo → uprav tiskárnu.</p>{znacka}</div>",
        f"<div class='slot slot-right'>{hl_z}{znacka}</div>",
    )
    return predni, zadni


def postav_html_karet(karty: list[Karta], *, nadpis: str, zadni_strana: str = "zadni") -> str:
    """Sestaví HTML tiskové sady. `zadni_strana`='zadni' (60min) | 'zadni_30' (30min)."""
    kal_predni, kal_zadni = _kalibrace()
    strany = [kal_predni, kal_zadni]
    for i in range(0, len(karty), 2):
        dvojice = karty[i:i + 2]
        a = dvojice[0]
        b = dvojice[1] if len(dvojice) > 1 else None
        # Přední arch: A vlevo, B vpravo.
        strany.append(_arch(_slot(a, "predni", "left"), _slot(b, "predni", "right")))
        # Zadní arch: STEJNÉ pořadí (levá zůstává levá po překlopení po delší straně).
        strany.append(_arch(_slot(a, zadni_strana, "left"), _slot(b, zadni_strana, "right")))
    telo = "".join(strany)
    return (
        f"<html><head><meta charset='utf-8'><title>{_html.escape(nadpis)}</title>"
        f"<style>{CSS_ARCH_KARTY}</style></head><body>{telo}</body></html>"
    )


def spocti_archy(html: str) -> int:
    """Počet archů (stran) v HTML — pro deterministickou validaci bez renderu."""
    return html.count("class='arch'")


def zkontroluj_pocet_stran(html: str, pocet_karet: int) -> bool:
    return spocti_archy(html) == pocet_stran(pocet_karet)


def uloz_pdf_karet(
    karty: list[Karta], cesta: str, *, nadpis: str, zadni_strana: str = "zadni"
) -> None:
    """Vyrenderuje tiskovou sadu do PDF (vyžaduje GTK; jinak SazbaNedostupna)."""
    html = postav_html_karet(karty, nadpis=nadpis, zadni_strana=zadni_strana)
    zapis_pdf(html, cesta)
