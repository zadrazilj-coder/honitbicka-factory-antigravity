"""Export hry do lidsky kontrolovatelných formátů (analýza §4, doporučení #2).

Jednosměrný pohled na data hry — nic negeneruje zpět:
- **Twee 3** (`export_twee`): soubor se dá přetáhnout do Twine a hra se
  okamžitě zobrazí jako klikatelný graf pasáží (kontrola proklikem).
- **Mermaid** (`export_mermaid`): blok `flowchart` pro README/průvodce/INDEX.

Zdroj pravdy zůstává `mapa.json` + `karty.json`; export skládá totéž, co
tiskne renderer karet (volby jsou data — viz modely.Karta).
"""

from __future__ import annotations

import html as _html

from honbicka.modely import Karta, Mapa, TypUzlu, _pismeno_volby

# Rozestup uzlů v Twine gridu (px) — jen kosmetika zobrazení.
_GRID_X, _GRID_Y, _NA_RADEK = 220, 160, 5


def _nazev_pasaze(cislo: int, nazev: str) -> str:
    """Jméno pasáže v Twee — musí být unikátní a bez hranatých závorek."""
    cisty = nazev.replace("[", "(").replace("]", ")").strip()
    return f"{cislo} {cisty}"


def export_twee(mapa: Mapa, karty: list[Karta] | None = None, *, nazev: str = "") -> str:
    """Twee 3 (https://specs.twinery.org/twee-3.html) z mapy a (volitelně) karet.

    Bez karet exportuje jen strukturu (názvy uzlů + hrany); s kartami přidá
    atmosféru, úvod a texty voleb. Odkaz `[[text->cíl]]` vzniká z hran grafu —
    stejný zdroj jako tištěná navigace."""
    karty_dle_cisla = {k.cislo: k for k in (karty or [])}
    jmena = {u.cislo: _nazev_pasaze(u.cislo, u.nazev) for u in mapa.uzly}
    radky: list[str] = [
        f":: StoryTitle\n{nazev or 'HONBIČKA'}\n",
        ':: StoryData\n{"ifid": "00000000-0000-4000-8000-000000000000", '
        '"format": "Harlowe", "format-version": "3.3.8"}\n',
    ]
    for i, u in enumerate(sorted(mapa.uzly, key=lambda x: x.cislo)):
        pozice = f"{100 + (i % _NA_RADEK) * _GRID_X},{100 + (i // _NA_RADEK) * _GRID_Y}"
        tagy = f"{u.typ.value} {u.profil.value}"
        if u.cislo == mapa.pozice_aha_uzel:
            tagy += " AHA"
        hlavicka = f':: {jmena[u.cislo]} [{tagy}] {{"position":"{pozice}"}}'
        telo: list[str] = []
        karta = karty_dle_cisla.get(u.cislo)
        if karta is not None:
            if karta.atmosfera:
                telo.append(f"//{karta.atmosfera}//")
            if karta.uvod.strip():
                telo.append(karta.uvod.strip())
            for j, v in enumerate(karta.volby):
                pod = f" (podmínka: {v.podminka})" if v.podminka else ""
                cil_jmeno = jmena.get(v.cil, str(v.cil))
                telo.append(f"[[{_pismeno_volby(j)}) {v.text.strip()}{pod}->{cil_jmeno}]]")
        else:
            for j, h in enumerate(u.hrany):
                pod = f" (podmínka: {h.podminka})" if h.podminka else ""
                cil_jmeno = jmena.get(h.cil, str(h.cil))
                telo.append(f"[[{_pismeno_volby(j)}) dál{pod}->{cil_jmeno}]]")
        if u.typ == TypUzlu.CIL and not telo:
            telo.append("KONEC — organizátor přečte epilog.")
        radky.append(hlavicka + "\n" + "\n".join(telo) + "\n")
    return "\n".join(radky)


def export_mermaid(mapa: Mapa) -> str:
    """Mermaid `flowchart TD`: uzly s typem, hrany s podmínkami, zvýrazněný
    AHA uzel a odlišené SIDE uzly (jen 60min)."""
    radky = ["flowchart TD"]
    for u in sorted(mapa.uzly, key=lambda x: x.cislo):
        popisek = _html.escape(f"{u.cislo} {u.nazev} ({u.typ.value})", quote=True)
        popisek = popisek.replace('"', "'")
        if u.typ == TypUzlu.CIL:
            radky.append(f'    n{u.cislo}(("{popisek}"))')
        else:
            radky.append(f'    n{u.cislo}["{popisek}"]')
    for u in mapa.uzly:
        for h in u.hrany:
            if h.podminka:
                pod = h.podminka.replace('"', "'").replace("|", "/")
                radky.append(f'    n{u.cislo} -->|"{pod}"| n{h.cil}')
            else:
                radky.append(f"    n{u.cislo} --> n{h.cil}")
    side = [f"n{u.cislo}" for u in mapa.uzly if u.profil.value == "SIDE"]
    radky.append("    classDef side fill:#eee,stroke:#999,stroke-dasharray: 5 5;")
    radky.append("    classDef aha fill:#ffd54f,stroke:#c00,stroke-width:3px;")
    if side:
        radky.append(f"    class {','.join(side)} side;")
    if mapa.uzel(mapa.pozice_aha_uzel) is not None:
        radky.append(f"    class n{mapa.pozice_aha_uzel} aha;")
    return "\n".join(radky) + "\n"
