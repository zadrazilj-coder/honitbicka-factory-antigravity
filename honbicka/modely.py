"""Datové modely (pydantic) pro HONBIČKA FACTORY.

Jediný zdroj tvarů dat mezi rolemi LLM a deterministickým kódem. Pro modely,
které jsou zároveň schématem pro *structured output* Ollamy, se JSON schema
získává přes `SCHEMA_*` konstanty dole (pole ``format`` v Ollama API).

Autorita herní mechaniky: engine/DODATKY_3.4.md > engine/SKILL.md. Modely tu
nekódují herní pravidla (od toho jsou validátory), jen jejich datový tvar.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Číselníky (enumy)
# --------------------------------------------------------------------------- #
class Archetyp(StrEnum):
    """Archetypy zvratu (SKILL.md §P0b). Losuje Python, ne LLM."""

    A1 = "A1"  # Antigamebook
    A2 = "A2"  # Falešný cíl
    A3 = "A3"  # Zadavatel je padouch
    A4 = "A4"  # Žádný antagonista
    A5 = "A5"  # Hráč je příčina
    A6 = "A6"  # Syntéza teorií
    A7 = "A7"  # Přímé řešení platí


class TypUzlu(StrEnum):
    """Typy uzlů mapy (SKILL.md §MAPA A TOPOLOGIE)."""

    ONBOARDING = "onboarding"
    ROZCESTI = "rozcesti"
    SBER = "sber"
    PRECHOD = "prechod"
    SLEPA = "slepa"
    JEDNOSMER = "jednosmer"
    SMYCKA = "smycka"
    STREZ = "strez"
    GATED = "gated"
    INFORMACE = "informace"
    POSTAVA = "postava"
    LECITEL = "lecitel"
    OBCHODNIK = "obchodnik"
    CIL = "cil"


class Profil(StrEnum):
    """Profil délky. Factory používá jen 30/60 (viz docs/rozhodnuti.md)."""

    CORE = "CORE"  # 30 min
    SIDE = "SIDE"  # jen v 60 min


class Obtiznost(StrEnum):
    LEHKA = "lehka"
    STREDNI = "stredni"
    TEZKA = "tezka"


class VekPasmo(StrEnum):
    """Factory věková pásma (spec §7/§8). Mapování na engine pásma řeší taxonomie.py."""

    V04_06 = "04-06"
    V06_09 = "06-09"
    V09_12 = "09-12"
    V12_15 = "12-15"
    V16PLUS = "16plus"


class Pravdivost(StrEnum):
    """Pravdivostní hodnota stopy (SKILL.md §INFORMACE JSOU ODMĚNA)."""

    PRAVDA = "pravda"
    ZAVADEJICI = "zavadejici"
    LEZ = "lez"


class StavHry(StrEnum):
    OK = "OK"
    FAILED = "FAILED"


# --------------------------------------------------------------------------- #
# Zadání (vstup)
# --------------------------------------------------------------------------- #
_FORMAT_TYMY_RE = re.compile(r"^tymy_(\d+)x(\d+)$")
_POVOLENE_FORMATY = {"jednotlivci", "dvojice", "volny_format"}


class Zadani(BaseModel):
    """Vstupní zadání jedné hry (YAML dle spec §8 nebo výstup téma-generátoru).

    `vek` je factory pásmo. `format_hracu` je buď 'jednotlivci' / 'dvojice' /
    'volny_format', nebo 'tymy_<n>x<m>' (max 4 týmy po max 4 — SKILL.md).
    """

    tema: str | None = Field(default=None, description="Téma hry; None → doplní téma-generátor")
    vek: VekPasmo
    format_hracu: str = Field(default="volny_format")
    prostredi: list[str] = Field(default_factory=lambda: ["les"])
    obtiznost: Obtiznost = Obtiznost.LEHKA
    ton: str | None = None
    jazyk: str = "cs"

    @field_validator("format_hracu")
    @classmethod
    def _zkontroluj_format(cls, v: str) -> str:
        if v in _POVOLENE_FORMATY:
            return v
        m = _FORMAT_TYMY_RE.match(v)
        if not m:
            raise ValueError(
                f"neplatný format_hracu '{v}'; povoleno: {_POVOLENE_FORMATY} nebo tymy_NxM"
            )
        pocet, velikost = int(m.group(1)), int(m.group(2))
        if not (1 <= pocet <= 4 and 1 <= velikost <= 4):
            raise ValueError("tymy: max 4 týmy po max 4 hráčích (SKILL.md)")
        return v

    @property
    def je_volny_format(self) -> bool:
        return self.format_hracu == "volny_format"

    def rozmery_tymu(self) -> tuple[int, int] | None:
        """Vrátí (pocet_tymu, velikost_tymu) pro 'tymy_NxM', jinak None."""
        m = _FORMAT_TYMY_RE.match(self.format_hracu)
        return (int(m.group(1)), int(m.group(2))) if m else None


# --------------------------------------------------------------------------- #
# Mapa (výstup ARCHITEKTA)
# --------------------------------------------------------------------------- #
class Hrana(BaseModel):
    """Orientovaná hrana grafu mapy."""

    cil: int = Field(description="Číslo cílového uzlu")
    podminka: str | None = Field(default=None, description="Gate: předmět/stav/světlo; None=volná")
    efekt: str | None = Field(default=None, description="Efekt volby (detekce prázdných voleb)")
    jednosmerna: bool = False
    fyzicka_narocnost: str = Field(default="low", description="'low' | 'high' (přístupnost, 3.4-6)")


class Uzel(BaseModel):
    """Uzel mapy = jedna karta (SKILL.md §MAPA, spec §3 ARCHITEKT)."""

    cislo: int
    nazev: str
    typ: TypUzlu
    region: str
    prostredi: str
    profil: Profil = Field(description="CORE (i v 30min) nebo SIDE (jen 60min)")
    predmety: list[str] = Field(default_factory=list)
    komponenty: list[str] = Field(default_factory=list, description="Komponenty artefaktu / světla")
    stavy: list[str] = Field(default_factory=list)
    body_aktivity: int = 0
    kostka: bool = False
    klicove_svedectvi: bool = Field(default=False, description="Nese stopu nutnou k pravdě (3.4-4)")
    hrany: list[Hrana] = Field(default_factory=list)


class Mapa(BaseModel):
    """Graf mapy jako DATA (výstup architekta). Validují validatory/*, ne LLM."""

    archetyp: Archetyp
    seed: int
    prah_aktivity: int = Field(description="Práh počítadla; násobek 5 v 80–120 (3.4-1)")
    pozice_aha_uzel: int = Field(description="Číslo uzlu, kde padne AHA odhalení")
    regiony: list[str] = Field(default_factory=list)
    uzly: list[Uzel]

    def uzel(self, cislo: int) -> Uzel | None:
        return next((u for u in self.uzly if u.cislo == cislo), None)

    @property
    def core_uzly(self) -> list[Uzel]:
        """Podgraf 30min verze = jen CORE uzly (spec §5)."""
        return [u for u in self.uzly if u.profil == Profil.CORE]

    def podgraf_core(self) -> Mapa:
        """Vrátí 30min mapu: jen CORE uzly a jen hrany mířící do CORE.

        Rozcestníky odkazující na SIDE mají v 30min variantě zadní stranu bez
        SIDE voleb (spec §5) — proto hrany do SIDE uzlů odpadají."""
        core_cisla = {u.cislo for u in self.uzly if u.profil == Profil.CORE}
        nove_uzly: list[Uzel] = []
        for u in self.uzly:
            if u.cislo not in core_cisla:
                continue
            kopie = u.model_copy(deep=True)
            kopie.hrany = [h for h in u.hrany if h.cil in core_cisla]
            nove_uzly.append(kopie)
        regiony = sorted({u.region for u in nove_uzly})
        return Mapa(
            archetyp=self.archetyp,
            seed=self.seed,
            prah_aktivity=self.prah_aktivity,
            pozice_aha_uzel=self.pozice_aha_uzel,
            regiony=regiony,
            uzly=nove_uzly,
        )


# --------------------------------------------------------------------------- #
# Koncept (narativní rozhodnutí — výstup ARCHITEKTA před mapou, FÁZE 1)
# --------------------------------------------------------------------------- #
class Koncept(BaseModel):
    """Narativní kostra hry (SKILL.md FÁZE 2, uloženo do koncept.md).

    Nese počty, které nejsou v grafu mapy (falešné teorie, pravdivé stopy,
    konce) a údaje pro registr (mechanismus řešení, klíčová rekvizita)."""

    archetyp: Archetyp
    tema: str
    zanr: str = ""
    mechanismus_reseni: str = Field(
        min_length=15, description="Jak se pravda odvodí (celá věta, pro registr)"
    )
    klicova_rekvizita: str = Field(default="", description="Hlavní rekvizita řešení (pro registr)")
    falesne_teorie: int = Field(description="Počet konkurenčních falešných teorií (P7)")
    pravdive_stopy: int = Field(description="Počet pravdivých stop (min dle §SKÁLOVÁNÍ)")
    konce: int = Field(description="Počet vrstev vítězství (P11)")
    slovnik_zakazana: list[str] = Field(default_factory=list, description="forbidden_terms žánru")

    @field_validator("mechanismus_reseni")
    @classmethod
    def _zkontroluj_vetu(cls, v: str) -> str:
        # O5: model občas vrátí snake_case token ("prunik_stop") místo věty —
        # takové tokeny dělají okna zákazů v registru bezcenná (R1). Vyžaduj
        # skutečnou větu (obsahuje mezeru, ne podtržítko).
        if "_" in v or " " not in v.strip():
            raise ValueError(
                "mechanismus_reseni musí být celá věta se slovy oddělenými mezerou "
                "(ne snake_case token jako 'prunik_stop')"
            )
        return v

    @field_validator("klicova_rekvizita")
    @classmethod
    def _zkontroluj_rekvizitu(cls, v: str) -> str:
        if "_" in v:
            raise ValueError("klicova_rekvizita nesmí obsahovat podtržítko (snake_case token)")
        return v


# --------------------------------------------------------------------------- #
# Karta (výstup VYPRAVĚČE)
# --------------------------------------------------------------------------- #
class Karta(BaseModel):
    """Text jedné karty. `zadni_30` je varianta zadní strany bez SIDE voleb
    (spec §5); je-li None, platí `zadni` pro obě délky."""

    cislo: int
    nazev: str
    typ: TypUzlu
    atmosfera: str = Field(description="Povinný atmosférický odstavec (300–500 znaků, 3.4-7)")
    predni: str = Field(description="Přední strana: příběh + volby")
    zadni: str = Field(description="Zadní strana (60min varianta / výchozí)")
    zadni_30: str | None = Field(default=None, description="Zadní strana bez SIDE voleb (30min)")


# --------------------------------------------------------------------------- #
# Redakční posudek (výstup REDAKTORA, LLM-judge)
# --------------------------------------------------------------------------- #
class RedakceVerdikt(BaseModel):
    """Verdikt jednoho redakčního checku R1–R7 (SKILL.md §VALIDACE Patro 2).

    `citace_karet` musí být DOSLOVNÉ úryvky z karet — orchestrátor je ověří
    grepem; bez existující citace je verdikt neplatný (spec §3, §12)."""

    check: str = Field(description="R1..R7")
    verdikt: bool = Field(description="True = prošlo")
    citace_karet: list[str] = Field(default_factory=list)
    zduvodneni: str = ""


class RedakceVsechnyVerdikty(BaseModel):
    """Všech 7 verdiktů R1–R7 v JEDNOM volání (L7/O13): dřív 7 sekvenčních
    thinking-ON volání redaktora trvalo v živém běhu ~15 min a často
    timeoutovalo. Jeden strukturovaný výstup se všemi checky najednou."""

    verdikty: list[RedakceVerdikt] = Field(
        description="Přesně 7 verdiktů, jeden pro každý check R1 až R7"
    )


# --------------------------------------------------------------------------- #
# Reporty (deterministické výstupy)
# --------------------------------------------------------------------------- #
class FitCheck(BaseModel):
    """Výsledek reálného renderu jedné strany karty (spec §6)."""

    karta: int
    strana: str  # "predni" | "zadni" | "zadni_30"
    vyska_mm: float
    limit_mm: float
    verdikt: bool


class SimulaceReport(BaseModel):
    """Výsledek jednoho BFS průchodu (spec §4 FÁZE 2)."""

    profil: str  # "30" | "60"
    delka_min: float
    pozice_aha_pct: float
    aha_v_pasmu: bool
    dosahl_cile: bool


class Report(BaseModel):
    """Souhrnný report jedné hry (report.json)."""

    slug: str
    seed: int
    archetyp: Archetyp
    iterace: int = 0
    stav: StavHry = StavHry.OK
    validation_report: dict[str, Any] = Field(default_factory=dict)
    editorial_report: list[RedakceVerdikt] = Field(default_factory=list)
    simulation_reports: list[SimulaceReport] = Field(default_factory=list)
    fit_check: list[FitCheck] = Field(default_factory=list)
    chyby: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Hra (celý balíček = jeden princip, dva profily)
# --------------------------------------------------------------------------- #
class Hra(BaseModel):
    """Kompletní vyrobená hra: jeden princip → profily 30 (CORE) i 60 (master)."""

    slug: str
    zadani: Zadani
    koncept: str = ""
    mapa: Mapa | None = None  # None při FAILED hře (FÁZE 1 neuspěla)
    karty: list[Karta] = Field(default_factory=list)
    report: Report


# --------------------------------------------------------------------------- #
# Schémata pro structured output Ollamy
# --------------------------------------------------------------------------- #
def _llm_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema pydantic modelu pro pole ``format`` v Ollama /api/chat."""
    return model.model_json_schema()


# Explicitní registr schémat, na která se spoléhají role LLM.
SCHEMA_ZADANI = _llm_schema(Zadani)
SCHEMA_KONCEPT = _llm_schema(Koncept)
SCHEMA_MAPA = _llm_schema(Mapa)
SCHEMA_KARTA = _llm_schema(Karta)
SCHEMA_REDAKCE = _llm_schema(RedakceVerdikt)
SCHEMA_REDAKCE_VSECHNY = _llm_schema(RedakceVsechnyVerdikty)
