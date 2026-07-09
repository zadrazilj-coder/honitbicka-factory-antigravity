from __future__ import annotations

import html as _html
from honbicka.sazba.render import zapis_pdf

CSS_OBALKA = """
@page { size: 297mm 210mm; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; }
.obalka-arch { position: relative; width: 297mm; height: 210mm; overflow: hidden; }
.panel { position: absolute; top: 0; width: 148.5mm; height: 210mm; padding: 12mm 15mm; }
.panel-left { left: 0; border-right: 0.2mm dashed #000; }
.panel-right { left: 148.5mm; position: relative; }

.nadpis { font-size: 16pt; font-weight: bold; border-bottom: 1mm solid #000; padding-bottom: 2mm; margin-bottom: 4mm; }
.sekce { margin-bottom: 4mm; }
.sekce h3 { margin: 0 0 2mm 0; font-size: 11pt; text-transform: uppercase; }
.instrukce { font-size: 8.5pt; line-height: 1.4; color: #333; }
.instrukce ol { margin: 0; padding-left: 5mm; }

.sleeve-label { position: absolute; bottom: 10mm; left: 15mm; font-size: 8pt; color: #777; }

/* Chlopne na prave strane (sleeve back) */
.flap-box { position: absolute; left: 10mm; width: 128.5mm; height: 35mm; }
.flap-A { top: 82mm; }
.flap-B { top: 122mm; }
.flap-C { top: 162mm; }

.flap-cut-line {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-top: 0.3mm solid #000;
    border-bottom: 0.3mm solid #000;
    border-right: 0.3mm solid #000;
    border-left: 0.3mm dashed #000; /* fold line */
    background: #fbfbfb;
    padding: 3mm 4mm;
}
.flap-title { font-weight: bold; font-size: 11pt; margin-bottom: 1mm; }
.flap-desc { font-size: 7.5pt; color: #555; line-height: 1.2; }
"""

def postav_html_obalky(tema: str) -> str:
    esc = _html.escape
    
    instrukce_html = (
        "<ol>"
        "<li><b>Vytiskni jednostranně</b> na tvrdší papír (karton A4).</li>"
        "<li><b>Nařízni chlopně A, B, C</b> podél <b>plných (solid)</b> čar na pravé straně. "
        "Čárkovanou (dashed) čáru vlevo na chlopni <b>neřež</b>, pouze ohni – tvoří pant chlopně.</li>"
        "<li><b>Přehni celý arch napůl</b> podél středové čárkované čáry.</li>"
        "<li><b>Slep nebo zalep izolepou</b> horní a spodní okraj kapsy k sobě. "
        "Vznikne kapsa (sleeve) otevřená z vnější strany.</li>"
        "<li><b>Zasuň kartu</b> dovnitř. Při hře otoč kapsu a odklop pouze chlopeň pro zvolenou akci!</li>"
        "</ol>"
    )

    chlopne_html = []
    for p in ("A", "B", "C"):
        chlopne_html.append(
            f"<div class='flap-box flap-{p}'>"
            f"<div class='flap-cut-line'>"
            f"<div class='flap-title'>CHLOPEŇ {p}</div>"
            f"<div class='flap-desc'>Nařízni plnou čáru ze tří stran. Ohni čárkovanou čáru vlevo. "
            f"Zde uvidíš pouze výsledek volby {p}.</div>"
            f"</div>"
            f"</div>"
        )

    html = (
        f"<html><head><meta charset='utf-8'><title>Karetní obálka</title>"
        f"<style>{CSS_OBALKA}</style></head><body>"
        f"<div class='obalka-arch'>"
        f"<div class='panel panel-left'>"
        f"<div class='nadpis'>KARETNÍ OBÁLKA</div>"
        f"<div class='sekce'>"
        f"<h3>Téma hry</h3>"
        f"<p style='font-size:12pt; font-style:italic;'>{esc(tema)}</p>"
        f"</div>"
        f"<div class='sekce'>"
        f"<h3>Návod k sestavení a použití</h3>"
        f"<div class='instrukce'>{instrukce_html}</div>"
        f"</div>"
        f"<div class='sleeve-label'>HONBIČKA Factory v3.4 — Obálka s chlopněmi pro utajení cesty</div>"
        f"</div>"
        f"<div class='panel panel-right'>"
        f"<div style='font-size:10pt; font-weight:bold; margin-bottom:5mm; border-bottom:0.2mm solid #000; padding-bottom:2mm;'>"
        f"ZADNÍ STRANA OBÁLKY — CHLOPNĚ PRO AKCE"
        f"</div>"
        f"{''.join(chlopne_html)}"
        f"</div>"
        f"</div>"
        f"</body></html>"
    )
    return html

def uloz_pdf_obalky(cesta: str, tema: str) -> None:
    html = postav_html_obalky(tema)
    zapis_pdf(html, cesta)
