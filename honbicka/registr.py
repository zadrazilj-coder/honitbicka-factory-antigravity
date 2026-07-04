"""Registr her + okna zákazů (spec §7, SKILL.md §KROK 0b).

`skiny/registr.md` je append-only markdown tabulka, kterou orchestrátor parsuje
strojově. Okna zákazů: archetyp z posledních 3 her, mechanismus a rekvizity
z posledních 5. Jeden princip = jeden záznam se dvěma profily (spec §5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from honbicka.modely import Archetyp

_SLOUPCE = ["Datum", "Slug", "Archetyp", "Mechanismus", "Rekvizity",
            "Žánr/publikum", "Profily", "Seed"]
_HLAVICKA = "| " + " | ".join(_SLOUPCE) + " |"
_ODDELOVAC = "| " + " | ".join("---" for _ in _SLOUPCE) + " |"

# Velikosti oken zákazů (SKILL.md §KROK 0b).
OKNO_ARCHETYP = 3
OKNO_MECHANISMUS = 5
OKNO_REKVIZITY = 5


@dataclass
class ZaznamRegistru:
    datum: str
    slug: str
    archetyp: str
    mechanismus: str
    rekvizity: str
    zanr_publikum: str
    profily: str
    seed: int

    def _bunky(self) -> list[str]:
        return [self.datum, self.slug, self.archetyp, self.mechanismus,
                self.rekvizity, self.zanr_publikum, self.profily, str(self.seed)]

    def radek(self) -> str:
        # `|` v obsahu by rozbil tabulku → nahradíme.
        bunky = [b.replace("|", "/").strip() for b in self._bunky()]
        return "| " + " | ".join(bunky) + " |"


def nacti_registr(cesta: str = "skiny/registr.md") -> list[ZaznamRegistru]:
    """Načte záznamy (chronologicky, nejstarší první). Chybí-li soubor → []."""
    if not os.path.exists(cesta):
        return []
    zaznamy: list[ZaznamRegistru] = []
    with open(cesta, encoding="utf-8") as f:
        for radek in f:
            radek = radek.strip()
            if not radek.startswith("|"):
                continue
            bunky = [b.strip() for b in radek.strip("|").split("|")]
            if len(bunky) != len(_SLOUPCE):
                continue
            if bunky[0] in ("Datum", "---") or set(bunky[0]) == {"-"}:
                continue  # hlavička / oddělovač
            try:
                seed = int(bunky[7])
            except ValueError:
                continue
            zaznamy.append(ZaznamRegistru(
                datum=bunky[0], slug=bunky[1], archetyp=bunky[2], mechanismus=bunky[3],
                rekvizity=bunky[4], zanr_publikum=bunky[5], profily=bunky[6], seed=seed,
            ))
    return zaznamy


def zapis_zaznam(zaznam: ZaznamRegistru, cesta: str = "skiny/registr.md") -> None:
    """Append řádek; udrží validní markdown tabulku (založí hlavičku, chybí-li)."""
    os.makedirs(os.path.dirname(cesta) or ".", exist_ok=True)
    nova = not os.path.exists(cesta) or os.path.getsize(cesta) == 0
    with open(cesta, "a", encoding="utf-8") as f:
        if nova:
            f.write("# Registr her HONBIČKA\n\n")
            f.write(_HLAVICKA + "\n" + _ODDELOVAC + "\n")
        f.write(zaznam.radek() + "\n")


def zakazana_okna(zaznamy: list[ZaznamRegistru]) -> dict[str, set[str]]:
    """Zakázané hodnoty pro novou hru: archetyp z posl. 3, mechanismus a
    rekvizity z posl. 5 (SKILL.md §KROK 0b)."""
    rekv: set[str] = set()
    for z in zaznamy[-OKNO_REKVIZITY:]:
        rekv.update(r.strip().lower() for r in z.rekvizity.split(",") if r.strip())
    return {
        "archetyp": {z.archetyp for z in zaznamy[-OKNO_ARCHETYP:]},
        "mechanismus": {z.mechanismus.strip().lower() for z in zaznamy[-OKNO_MECHANISMUS:]},
        "rekvizity": rekv,
    }


def zakazane_archetypy(zaznamy: list[ZaznamRegistru]) -> frozenset[Archetyp]:
    """Množina archetypů, které se v nové hře nesmí opakovat (posl. 3 hry)."""
    okna = zakazana_okna(zaznamy)
    vysledek: set[Archetyp] = set()
    for kod in okna["archetyp"]:
        try:
            vysledek.add(Archetyp(kod))
        except ValueError:
            continue
    return frozenset(vysledek)
