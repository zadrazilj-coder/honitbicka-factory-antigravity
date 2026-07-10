"""Třídění hotových her a mapování věkových pásem.

Dvě sady věkových pásem (viz docs/rozhodnuti.md):
- **factory** (spec §7/§8, YAML a složky `hotove_hry/`),
- **engine** (SKILL.md §VĚKOVÁ ADAPTACE, řídí obsah karet).

`taxonomie.py` mezi nimi převádí a skládá cílovou cestu ve `hotove_hry/`.
"""

from __future__ import annotations

import os
import shutil

from honbicka.modely import VekPasmo, Zadani

# Mapování factory pásmo → engine pásmo (docs/rozhodnuti.md 2026-07-03).
VEK_FACTORY_NA_ENGINE: dict[VekPasmo, str] = {
    VekPasmo.V04_06: "4-6",
    VekPasmo.V06_09: "7-10",
    VekPasmo.V09_12: "11-14",
    VekPasmo.V12_15: "15-18",
    VekPasmo.V16PLUS: "dospeli",
}


def vek_pro_engine(vek: VekPasmo) -> str:
    """Vrátí engine věkové pásmo pro dané factory pásmo."""
    return VEK_FACTORY_NA_ENGINE[vek]


def slozka_formatu(format_hracu: str) -> str:
    """Název podsložky dle formátu hráčů (spec §7).

    'tymy_4x4' → 'tymy_4x4'; 'volny_format' → 'volny_format'; atd.
    """
    return format_hracu


def cesta_hotove_hry(zadani: Zadani, slug: str, profil_min: int) -> str:
    """Relativní cesta ve `hotove_hry/` (spec §7).

    Např.: hotove_hry/vek_06-09/tymy_4x4/lesni-detektivka_30min
    """
    if profil_min not in (30, 60):
        raise ValueError("factory používá jen profily 30 a 60 (docs/rozhodnuti.md)")
    slozka = slozka_formatu(zadani.format_hracu)
    return f"hotove_hry/vek_{zadani.vek.value}/{slozka}/{slug}_{profil_min}min"


# Mapování názvů výstupů skinu na profil (30/60).
_VYSTUPY_PROFILU = {
    30: ["karty_30min.pdf", "herni_list_30min.pdf", "pruvodce_30min.pdf"],
    60: ["karty_60min.pdf", "herni_list_60min.pdf", "pruvodce_60min.pdf"],
}


def _index_md(zadani: Zadani, slug: str, profil_min: int, anotace: str, soubory: list[str]) -> str:
    tisk = "\n".join(f"- {s}" for s in soubory) or "- (PDF zatím nevygenerováno — chybí GTK)"
    return (
        f"# {slug} — {profil_min} min\n\n"
        f"**Věk:** {zadani.vek.value} · **Formát:** {zadani.format_hracu} · "
        f"**Prostředí:** {', '.join(zadani.prostredi)}\n\n"
        f"{anotace}\n\n## Co vytisknout\n{tisk}\n"
    )


def zatrid_hru(
    zadani: Zadani, slug: str, zdrojovy_skin_dir: str, *, anotace: str = ""
) -> list[str]:
    """Zkopíruje finální výstupy skinu do `hotove_hry/…` (oba profily) a založí
    INDEX.md bez spoilerů (spec §7). Zahrnuje automatický export twee mapy
    do složky hry a centrálního adresáře `mapy/`.
    """
    import json
    from honbicka.modely import Mapa, Karta
    from honbicka.export import export_twee

    # Načteme mapu a karty ze skinu
    mapa = None
    karty = None
    mapa_cesta = os.path.join(zdrojovy_skin_dir, "mapa.json")
    karty_cesta = os.path.join(zdrojovy_skin_dir, "karty.json")
    if os.path.exists(mapa_cesta):
        with open(mapa_cesta, encoding="utf-8") as f:
            mapa = Mapa.model_validate_json(f.read())
    if os.path.exists(karty_cesta):
        with open(karty_cesta, encoding="utf-8") as f:
            karty = [Karta.model_validate(k) for k in json.load(f)]

    vytvorene: list[str] = []
    anot = anotace or f"Venkovní karetní dobrodružství „{zadani.tema or slug}“."

    # Uložíme twee do zdrojové složky skinu
    if mapa is not None:
        twee_obsah = export_twee(mapa, karty, nazev=slug)
        with open(os.path.join(zdrojovy_skin_dir, f"{slug}.twee"), "w", encoding="utf-8") as f:
            f.write(twee_obsah)

    for profil in (30, 60):
        cil = cesta_hotove_hry(zadani, slug, profil)
        os.makedirs(cil, exist_ok=True)
        zkopirovane: list[str] = []
        for soubor in _VYSTUPY_PROFILU[profil]:
            zdroj = os.path.join(zdrojovy_skin_dir, soubor)
            if os.path.exists(zdroj):
                shutil.copy2(zdroj, os.path.join(cil, soubor))
                zkopirovane.append(soubor)

        # Uložíme twee mapu do složky hry a centrální mapy/
        if mapa is not None:
            twee_cesta_hry = os.path.join(cil, f"mapa_{profil}min.twee")
            with open(twee_cesta_hry, "w", encoding="utf-8") as f:
                f.write(export_twee(mapa, karty, nazev=slug))
            zkopirovane.append(f"mapa_{profil}min.twee")

            # Uložíme do centrální mapy/
            os.makedirs("mapy", exist_ok=True)
            twee_cesta_central = os.path.join("mapy", f"{slug}_{profil}min.twee")
            with open(twee_cesta_central, "w", encoding="utf-8") as f:
                f.write(export_twee(mapa, karty, nazev=slug))

        index = os.path.join(cil, "INDEX.md")
        with open(index, "w", encoding="utf-8") as f:
            f.write(_index_md(zadani, slug, profil, anot, zkopirovane))
        vytvorene.append(cil)
    return vytvorene
