"""Topologické kontroly grafu mapy (SKILL.md §VALIDACE Patro 1, body 1–4).

Dosažitelnost, softlock, rytmus (dvě `sber` za sebou), prázdné volby, integrita
hran, garantovaný návrat u smyček/slepých/jednosměrek, topologická minima
(proporcionálně počtu karet). Vše deterministicky, ŽÁDNÝ LLM.

Rozsah dokončitelnosti dle archetypu (bod 6) a komponent (bod 7) patří do M3
(architekt + koncept dodají řešení/komponenty) — viz docs/rozhodnuti.md.
"""

from __future__ import annotations

from collections import deque

from honbicka.modely import Hrana, Mapa, TypUzlu, Uzel
from honbicka.validatory import VysledekValidace

# Plná topologická minima platí od ~20 karet (SKILL.md §MAPA); menší hry
# proporcionálně.
PLNA_MINIMA_OD_KARET = 20
MIN_VETVE = 3
MIN_SMYCKY = 2
MIN_SLEPE = 2
MIN_JEDNOSMERKY = 2


def _start_uzel(mapa: Mapa) -> Uzel | None:
    """Startovní uzel = onboarding s nejmenším číslem; fallback nejmenší číslo."""
    onboardy = [u for u in mapa.uzly if u.typ == TypUzlu.ONBOARDING]
    if onboardy:
        return min(onboardy, key=lambda u: u.cislo)
    return min(mapa.uzly, key=lambda u: u.cislo) if mapa.uzly else None


def _dopredu(mapa: Mapa) -> dict[int, list[int]]:
    return {u.cislo: [h.cil for h in u.hrany] for u in mapa.uzly}


def _dosazitelne_z(mapa: Mapa, start: int) -> set[int]:
    graf = _dopredu(mapa)
    vid: set[int] = set()
    fronta = deque([start])
    while fronta:
        n = fronta.popleft()
        if n in vid:
            continue
        vid.add(n)
        for c in graf.get(n, []):
            if c not in vid:
                fronta.append(c)
    return vid


def _muze_dosahnout_cil(mapa: Mapa) -> set[int]:
    """Množina uzlů, ze kterých vede cesta do některého `cil` (reverzní BFS)."""
    cile = {u.cislo for u in mapa.uzly if u.typ == TypUzlu.CIL}
    rev: dict[int, list[int]] = {u.cislo: [] for u in mapa.uzly}
    for u in mapa.uzly:
        for h in u.hrany:
            if h.cil in rev:
                rev[h.cil].append(u.cislo)
    vid: set[int] = set()
    fronta = deque(cile)
    while fronta:
        n = fronta.popleft()
        if n in vid:
            continue
        vid.add(n)
        for p in rev.get(n, []):
            if p not in vid:
                fronta.append(p)
    return vid


def _minima_pro(pocet_karet: int) -> tuple[int, int, int, int]:
    """Proporcionální topologická minima (SKILL.md §MAPA)."""
    if pocet_karet >= PLNA_MINIMA_OD_KARET:
        return MIN_VETVE, MIN_SMYCKY, MIN_SLEPE, MIN_JEDNOSMERKY
    faktor = pocet_karet / PLNA_MINIMA_OD_KARET
    skaluj = lambda m: max(1, round(m * faktor))  # noqa: E731
    return skaluj(MIN_VETVE), skaluj(MIN_SMYCKY), skaluj(MIN_SLEPE), skaluj(MIN_JEDNOSMERKY)


def zkontroluj_topologii(mapa: Mapa) -> VysledekValidace:
    """Body 1–4 + integrita hran + garantovaný návrat + topologická minima."""
    v = VysledekValidace()
    if not mapa.uzly:
        v.selhani("prázdná mapa")
        return v

    cisla = {u.cislo for u in mapa.uzly}
    if len(cisla) != len(mapa.uzly):
        v.selhani("duplicitní čísla uzlů")

    # Integrita hran: každý cíl existuje.
    for u in mapa.uzly:
        for h in u.hrany:
            if h.cil not in cisla:
                v.selhani(f"uzel {u.cislo}: hrana míří na neexistující uzel {h.cil}")

    start = _start_uzel(mapa)
    cile = [u for u in mapa.uzly if u.typ == TypUzlu.CIL]
    if not cile:
        v.selhani("mapa nemá žádný uzel typu 'cil'")

    # 1. Dosažitelnost: cíl ze startu; žádný osiřelý uzel.
    if start is not None:
        dostupne = _dosazitelne_z(mapa, start.cislo)
        for u in mapa.uzly:
            if u.cislo not in dostupne:
                v.selhani(
                    f"uzel {u.cislo} ({u.nazev}) je osiřelý (nedosažitelný ze startu)",
                    f"přidej hranu vedoucí k uzlu {u.cislo}",
                )
        if cile and not any(c.cislo in dostupne for c in cile):
            v.selhani("žádný cíl není dosažitelný ze startu", "propoj start s cílem")

    # 2. Softlock: každý ne-cil má východ; každý ne-cil dosáhne cíle.
    umi_do_cile = _muze_dosahnout_cil(mapa)
    for u in mapa.uzly:
        if u.typ == TypUzlu.CIL:
            continue
        if not u.hrany:
            v.selhani(f"uzel {u.cislo} ({u.nazev}) nemá východ (softlock)")
        elif u.cislo not in umi_do_cile:
            v.selhani(
                f"uzel {u.cislo} ({u.nazev}) se nemůže vrátit k cíli (softlock)",
                f"zajisti návratovou hranu z uzlu {u.cislo}",
            )

    # 3. Rytmus: žádné dvě 'sber' za sebou.
    for u in mapa.uzly:
        if u.typ != TypUzlu.SBER:
            continue
        for h in u.hrany:
            cil_u = mapa.uzel(h.cil)
            if cil_u is not None and cil_u.typ == TypUzlu.SBER:
                v.selhani(
                    f"dvě 'sber' za sebou: {u.cislo}→{h.cil}",
                    "vlož mezi ně oddechový uzel (čtení/hádanka/rozhodnutí)",
                )

    # 4. Prázdné volby: dvě hrany se shodným cílem i efektem.
    for u in mapa.uzly:
        videno: set[tuple[int, str | None]] = set()
        for h in u.hrany:
            klic = (h.cil, h.efekt)
            if klic in videno:
                v.selhani(
                    f"uzel {u.cislo}: prázdná volba (shodný cíl i efekt: {h.cil})",
                    "dej volbám různé cíle nebo různé efekty",
                )
            videno.add(klic)

    # Topologická minima (proporcionálně).
    n = len(mapa.uzly)
    min_vetve, min_smycky, min_slepe, min_jednosmer = _minima_pro(n)
    vetve = sum(1 for u in mapa.uzly if len(u.hrany) >= 2)
    smycky = sum(1 for u in mapa.uzly if u.typ == TypUzlu.SMYCKA)
    slepe = sum(1 for u in mapa.uzly if u.typ == TypUzlu.SLEPA)
    # Jednosměrky: uzly typu jednosmer NEBO hrany označené jednosmerna (vč.
    # bezpečnostních jednosměrek — dodatek 3.4-5).
    jednosmer = sum(1 for u in mapa.uzly if u.typ == TypUzlu.JEDNOSMER)
    jednosmer += sum(1 for u in mapa.uzly for h in u.hrany if h.jednosmerna)
    if vetve < min_vetve:
        v.selhani(f"málo větví: {vetve} < {min_vetve}")
    if smycky < min_smycky:
        v.selhani(f"málo smyček: {smycky} < {min_smycky}")
    if slepe < min_slepe:
        v.selhani(f"málo slepých uliček: {slepe} < {min_slepe}")
    if jednosmer < min_jednosmer:
        v.selhani(f"málo jednosměrek: {jednosmer} < {min_jednosmer}")

    # V6/dodatek 3.4-6 (přístupnost): uzel s klíčovým svědectvím musí mít ≥1
    # fyzicky nenáročnou VSTUPNÍ hranu, ať se k němu dostanou i hráči s
    # omezenou pohyblivostí — nesmí být podmíněné jen náročnou (`high`) cestou.
    vstupni: dict[int, list[Hrana]] = {u.cislo: [] for u in mapa.uzly}
    for u in mapa.uzly:
        for h in u.hrany:
            if h.cil in vstupni:
                vstupni[h.cil].append(h)
    for u in mapa.uzly:
        if not u.klicove_svedectvi:
            continue
        hrany_do = vstupni.get(u.cislo, [])
        if hrany_do and not any(h.fyzicka_narocnost == "low" for h in hrany_do):
            v.selhani(
                f"uzel {u.cislo} ({u.nazev}) nese klíčové svědectví, ale žádná "
                "vstupní hrana není fyzicky nenáročná (dodatek 3.4-6)",
                f"nastav fyzicka_narocnost='low' aspoň jedné hraně vedoucí do uzlu {u.cislo}",
            )

    return v
