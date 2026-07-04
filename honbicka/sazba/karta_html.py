"""HTML fragment jedné strany karty (sdílí M4 fit-check i M5 sazba).

Přední strana = povinný atmosférický odstavec + příběh/volby. Zadní strana =
výsledek/sekce. Text se escapuje; strukturu (arch A5, řez, duplex) řeší až M5.
"""

from __future__ import annotations

import html as _html

from honbicka.modely import Karta


def karta_strana_html(karta: Karta, strana: str) -> str:
    """Vrátí vnitřní HTML karty pro danou stranu: 'predni' | 'zadni' | 'zadni_30'."""
    esc = _html.escape
    if strana == "predni":
        return (
            f"<div class='karta-predni'>"
            f"<p class='atmosfera'>{esc(karta.atmosfera)}</p>"
            f"<div class='predni'>{esc(karta.predni)}</div>"
            f"</div>"
        )
    if strana == "zadni_30":
        text = karta.zadni_30 or karta.zadni
    else:
        text = karta.zadni
    return f"<div class='karta-zadni'>{esc(text)}</div>"
