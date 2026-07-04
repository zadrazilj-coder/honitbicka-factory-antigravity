"""Načítání YAML zadání/plánů a dávkový běh (spec §8).

`honbicka gen` = jedna hra z YAML; `honbicka batch` = N her z plánu (téma
generuje téma-generátor s diverzitou proti registru). FAILED hra nezastaví
dávku (spec §10).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml
from pydantic import BaseModel

from honbicka.feedback import nacti_feedbacky
from honbicka.llm import OllamaKlient
from honbicka.modely import Obtiznost, VekPasmo, Zadani
from honbicka.orchestrator import vygeneruj_tema, vyrob_hru
from honbicka.registr import nacti_registr
from honbicka.validatory.sazba import Measurer


class BatchPolozka(BaseModel):
    """Jedna kombinace věk × formát × počet her (spec §8, bez tématu)."""

    vek: VekPasmo
    format_hracu: str = "volny_format"
    pocet: int = 1
    prostredi: list[str] | None = None
    obtiznost: Obtiznost | None = None


def nacti_zadani(cesta: str) -> Zadani:
    """Načte a zvaliduje YAML zadání jedné hry (spec §8)."""
    with open(cesta, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Zadani.model_validate(data)


def nacti_plan(cesta: str) -> list[BatchPolozka]:
    """Načte batch plán: buď seznam položek, nebo dict s klíčem 'hry'/'polozky'."""
    with open(cesta, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if isinstance(data, dict):
        data = data.get("hry") or data.get("polozky") or []
    return [BatchPolozka.model_validate(p) for p in data]


@dataclass
class DavkaVysledek:
    slug: str
    stav: str
    seed: int
    chyby: list[str] = field(default_factory=list)


@dataclass
class DavkaReport:
    vysledky: list[DavkaVysledek] = field(default_factory=list)

    @property
    def celkem(self) -> int:
        return len(self.vysledky)

    @property
    def uspesnych(self) -> int:
        return sum(1 for v in self.vysledky if v.stav == "OK")

    @property
    def failed(self) -> int:
        return self.celkem - self.uspesnych


def spust_davku(
    plan: list[BatchPolozka],
    klient: OllamaKlient,
    *,
    measurer: Measurer | None = None,
    skiny_dir: str = "skiny",
    registr_cesta: str = "skiny/registr.md",
    zatridit: bool = True,
) -> DavkaReport:
    """Vyrobí N her přes noc. Každá hra: téma-generátor (diverzita) → vyrob_hru.
    FAILED hra (LLM/validace/výjimka) nezastaví dávku (spec §10)."""
    report = DavkaReport()
    for polozka in plan:
        for _ in range(polozka.pocet):
            try:
                zaznamy = nacti_registr(registr_cesta)
                feedbacky = nacti_feedbacky(skiny_dir)
                zadani = vygeneruj_tema(klient, polozka.vek, polozka.format_hracu,
                                        zaznamy, feedbacky)
                zmeny = {}
                if polozka.prostredi:
                    zmeny["prostredi"] = polozka.prostredi
                if polozka.obtiznost:
                    zmeny["obtiznost"] = polozka.obtiznost
                if zmeny:
                    zadani = zadani.model_copy(update=zmeny)
                hra = vyrob_hru(zadani, klient, measurer=measurer, skiny_dir=skiny_dir,
                                registr_cesta=registr_cesta, zatridit=zatridit)
                report.vysledky.append(DavkaVysledek(
                    slug=hra.slug, stav=hra.report.stav.value,
                    seed=hra.report.seed, chyby=hra.report.chyby))
            except Exception as exc:  # LLM/validace/IO — dávka pokračuje (spec §10)
                report.vysledky.append(DavkaVysledek(
                    slug="?", stav="FAILED", seed=-1, chyby=[f"{type(exc).__name__}: {exc}"]))
    return report
