"""HTML fragment jedné strany karty (sdílí M4 fit-check i M5 sazba).

Přední strana = povinný atmosférický odstavec + příběh/volby. Zadní strana =
výsledek/sekce. Text se escapuje; strukturu (arch A5, řez, duplex) řeší až M5.
"""

from __future__ import annotations

import html as _html

from honbicka.modely import Karta


def karta_strana_html(karta: Karta, strana: str) -> str:
    """Vrátí vnitřní HTML karty pro danou stranu:
    'predni' | 'predni_30' | 'zadni' | 'zadni_30'.

    Strany jsou deterministicky renderované pohledy na `Karta.volby`
    (viz modely.Karta) — *_30 varianty filtrují SIDE volby (spec §5)."""
    esc = _html.escape
    if strana in ("predni", "predni_30"):
        text = karta.predni_30 if strana == "predni_30" else karta.predni
        return (
            f"<div class='karta-predni'>"
            f"<p class='atmosfera'>{esc(karta.atmosfera)}</p>"
            f"<div class='predni'>{esc(text)}</div>"
            f"</div>"
        )
    jen_core = (strana == "zadni_30")
    volby = karta._volby_pro(jen_core)
    zaver_text = karta.zaver.strip()
    
    html_volby = []
    for i, v in enumerate(volby):
        pismeno = "ABCDEFGH"[i] if i < 8 else str(i + 1)
        html_volby.append(
            f"<div class='volba volba-{pismeno}'>"
            f"<b>{pismeno})</b> {esc(v.vysledek.strip())} &rarr; <b>karta {v.cil}</b>"
            f"</div>"
        )
    
    html_zaver = f"<div class='zaver'>{esc(zaver_text)}</div>" if zaver_text else ""
    html_volby_container = (
        f"<div class='volby-zadni'>{''.join(html_volby)}</div>"
        if html_volby else "<div class='volby-zadni'><i>Příběh na této kartě končí.</i></div>"
    )
    
    return f"<div class='karta-zadni'>{html_zaver}{html_volby_container}</div>"
