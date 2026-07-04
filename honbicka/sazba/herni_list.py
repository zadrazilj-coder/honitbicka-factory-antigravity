"""Herní list A5 (spec §6): počítadlo po 5, inventář, kruhy komponent, zápisník
stop, checkboxy vedlejších nitek, pole „moje teorie" dle formátu, pravidla."""

from __future__ import annotations

import html as _html
import math

from honbicka.sazba.styl import CSS_A5_LIST, SYM_KOSTKA


def _pocitadlo(prah: int) -> str:
    """Boxy počítadla seskupené po 5 až k prahu (papírové počítadlo po pětkách)."""
    skupin = math.ceil(prah / 5)
    bloky = []
    for _s in range(skupin):
        okna = "".join("<span></span>" for _ in range(5))
        bloky.append(f"<span style='margin-right:3mm'>{okna}</span>")
    return f"<div class='pocitadlo'>{''.join(bloky)}</div><small>práh nápovědy: {prah}</small>"


def _pole_teorie(format_hracu: str) -> str:
    if format_hracu == "dvojice":
        vyzva = "Shodněte se na JEDNÉ teorii a oba se podepište:"
    elif format_hracu.startswith("tymy_"):
        vyzva = "SÁZKA TÝMU: zapište teorii (volitelně o body). Epilog vyhodnotí veřejně:"
    else:
        vyzva = "Zapiš, co si myslíš, že se doopravdy děje:"
    return (
        f"<h3>Moje teorie</h3><p>{vyzva}</p>"
        "<div style='border:0.2mm solid #000;height:28mm'></div>"
    )


def postav_html_herni_list(
    *, tema: str, prah: int, profil_min: int, format_hracu: str,
    pocet_komponent: int, pocet_nitek: int = 3, je_volny_format: bool = False,
) -> str:
    esc = _html.escape
    inv_slotu = 3 if profil_min == 30 else 5
    inventar = "".join("<div class='slot-inv'></div>" for _ in range(inv_slotu))
    kruhy = "".join(
        "<span style='display:inline-block;width:9mm;height:9mm;border:0.3mm solid #000;"
        "border-radius:50%;margin:1mm'></span>"
        for _ in range(pocet_komponent)
    )
    nitky = "".join(
        f"<div>☐ vedlejší nitka {i + 1}</div>" for i in range(pocet_nitek)
    )
    prvni_navsteva = (
        "<p><b>Pozor:</b> úkol na kartě plníš jen při PRVNÍ návštěvě.</p>"
        if je_volny_format else ""
    )
    telo = (
        f"<h1>{esc(tema)}</h1>"
        f"<h3>Počítadlo aktivity</h3>{_pocitadlo(prah)}"
        f"<h3>Inventář ({inv_slotu} sloty)</h3>{inventar}"
        f"<h3>Komponenty artefaktu</h3>{kruhy}"
        f"<h3>Zápisník stop</h3><div style='border:0.2mm solid #000;height:24mm'></div>"
        f"<h3>Vedlejší nitky</h3>{nitky}"
        f"{_pole_teorie(format_hracu)}"
        f"<h3>Pravidla</h3><p>{SYM_KOSTKA} Kostka nikdy nevyřazuje — neúspěch tě posune "
        f"jinudy (a je zábavnější). Stavy jsou léčitelné u léčitele.</p>{prvni_navsteva}"
    )
    return (
        f"<html><head><meta charset='utf-8'><style>{CSS_A5_LIST}</style></head>"
        f"<body>{telo}</body></html>"
    )
