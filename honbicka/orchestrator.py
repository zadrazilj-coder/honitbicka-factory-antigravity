"""Stavový stroj FÁZE 0–5 (spec §4). M3 implementuje FÁZE 0 a FÁZE 1.

FÁZE 0  registr → okna zákazů → losování (Python `random` se seedem)
FÁZE 1  architekt → koncept + mapa → validace (topologie+škálování+simulace);
        cílená opravná smyčka (max 4 iterace → relosování seedu; max 2×, pak FAIL)
FÁZE 2  simulace (součást FÁZE 1 validace v této implementaci)
FÁZE 3–5 vypravěč / sazba / registr — doplní M4–M6.

Zásada spec §3: LOSOVÁNÍ dělá Python, ne LLM. Seed se loguje (reprodukovatelnost).
"""

from __future__ import annotations

import json
import os
import random
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError

from honbicka.llm import HonbickaLLMError, OllamaKlient, Role
from honbicka.modely import (
    SCHEMA_KARTA,
    SCHEMA_KONCEPT,
    SCHEMA_MAPA,
    SCHEMA_REDAKCE,
    SCHEMA_ZADANI,
    Archetyp,
    FitCheck,
    Hra,
    Karta,
    Koncept,
    Mapa,
    Profil,
    RedakceVerdikt,
    Report,
    StavHry,
    Uzel,
    VekPasmo,
    Zadani,
)
from honbicka.registr import (
    ZaznamRegistru,
    nacti_registr,
    zakazane_archetypy,
    zapis_zaznam,
)
from honbicka.sazba.herni_list import postav_html_herni_list
from honbicka.sazba.karty_pdf import uloz_pdf_karet
from honbicka.sazba.pruvodce import postav_html_pruvodce
from honbicka.sazba.render import SazbaNedostupna, zapis_pdf
from honbicka.taxonomie import zatrid_hru
from honbicka.validatory import VysledekValidace
from honbicka.validatory.agregace import validuj_par_30_60
from honbicka.validatory.sazba import Measurer, _weasy_measurer, fit_check_karty
from honbicka.validatory.simulace import pasmo_aha
from honbicka.validatory.skalovani import SKALA, VEK_STROP, komponenty_rozsah

MAX_ITERACI_ARCHITEKT = 4  # spec §4 FÁZE 1
MAX_RELOSOVANI = 2  # spec §4 FÁZE 1
MAX_ITERACI_KARTA = 3  # spec §4 FÁZE 3

# Váhy archetypů (SKILL.md §P0b). Losuje Python.
ARCHETYP_VAHY: dict[Archetyp, int] = {
    Archetyp.A1: 30, Archetyp.A2: 15, Archetyp.A3: 12, Archetyp.A4: 12,
    Archetyp.A5: 10, Archetyp.A6: 9, Archetyp.A7: 12,
}


# --------------------------------------------------------------------------- #
# TÉMA-GENERÁTOR (auto režim, spec §3.1) — thinking OFF, temp 1.0
# --------------------------------------------------------------------------- #
def _normalizuj_obtiznost(hodnota: object) -> str:
    """Model občas vrátí diakritiku ('lehká') místo enum hodnoty ('lehka')."""
    text = unicodedata.normalize("NFKD", str(hodnota)).encode("ascii", "ignore").decode().lower()
    return text if text in {"lehka", "stredni", "tezka"} else "lehka"


def vygeneruj_tema(
    klient: OllamaKlient,
    vek: VekPasmo,
    format_hracu: str,
    zaznamy: list[ZaznamRegistru],
    feedbacky: list[str] | None = None,
) -> Zadani:
    """Navrhne téma/žánr/prostředí/tón lišící se od posledních 10 her (spec §3.1).

    Věk a formát řídí plán (ne LLM) — vloží se PŘED validací, protože model je
    nemusí vrátit správně (i se structured outputem). Enum obtížnosti se
    normalizuje (model vrací i diakritiku)."""
    posl = zaznamy[-10:]
    kontext = "; ".join(
        f"{z.zanr_publikum}·{z.archetyp}·{z.rekvizity}" for z in posl
    ) or "(zatím žádné hry)"
    fb = ""
    if feedbacky:
        fb = "\nPoznatky z playtestů (kalibruj obtížnost): " + " | ".join(feedbacky[:3])
    prompt = (
        f"Navrhni NOVÉ téma venkovní karetní hry pro věk {vek.value}, formát "
        f"{format_hracu}. MUSÍŠ se výrazně lišit (žánr/prostředí/zápletka) od "
        f"posledních her: {kontext}.{fb}\n"
        "Vrať zadání: tema, prostredi (seznam), obtiznost, ton."
    )
    data = klient.generuj_json(Role.TEMA_GENERATOR, prompt, SCHEMA_ZADANI)
    # Plán je autoritativní pro věk/formát; normalizuj enum obtížnosti.
    data["vek"] = vek.value
    data["format_hracu"] = format_hracu
    if "obtiznost" in data:
        data["obtiznost"] = _normalizuj_obtiznost(data["obtiznost"])
    return Zadani.model_validate(data)


# --------------------------------------------------------------------------- #
# FÁZE 0 — LOSOVÁNÍ
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LosovaneParametry:
    """Vylosované TVRDÁ omezení pro architekta (spec §3 „Losování")."""

    seed: int
    archetyp: Archetyp
    prah_aktivity: int
    pozice_aha_pct: float
    aha_pasmo: tuple[float, float]
    pocet_karet_60: int


def pocty_cile(zadani: Zadani) -> dict[str, int]:
    """Cílové koncept-počty pro 60min, s věkovým stropem (§SKÁLOVÁNÍ)."""
    s = SKALA[60]
    strop = zadani.vek in VEK_STROP
    return {
        "falesne_teorie": 1 if strop else s.falesne_teorie[1],
        "pravdive_stopy": s.pravdive_stopy_min,
        "konce": 2 if strop else s.konce[1],
    }


def losuj_parametry(
    zadani: Zadani, seed: int, zakazane_archetypy: frozenset[Archetyp] = frozenset()
) -> LosovaneParametry:
    """FÁZE 0: vylosuj archetyp (váhy, okna zákazů), práh (násobek 5 v 80–120),
    cílovou pozici AHA a počet karet. Deterministické dle seedu."""
    rng = random.Random(seed)
    povolene = [a for a in Archetyp if a not in zakazane_archetypy] or list(Archetyp)
    vahy = [ARCHETYP_VAHY[a] for a in povolene]
    archetyp = rng.choices(povolene, weights=vahy, k=1)[0]
    prah = rng.choice(list(range(80, 121, 5)))  # dodatek 3.4-1
    low, high = pasmo_aha(archetyp, zadani.je_volny_format)
    pozice = round(rng.uniform(low, high), 1)
    pocet_karet = rng.randint(*SKALA[60].karty)
    return LosovaneParametry(
        seed=seed, archetyp=archetyp, prah_aktivity=prah,
        pozice_aha_pct=pozice, aha_pasmo=(low, high), pocet_karet_60=pocet_karet,
    )


# --------------------------------------------------------------------------- #
# FÁZE 1 — ARCHITEKT (koncept + mapa) s opravnou smyčkou
# --------------------------------------------------------------------------- #
@dataclass
class VysledekFaze1:
    ok: bool
    koncept: Koncept | None = None
    mapa: Mapa | None = None
    parametry: LosovaneParametry | None = None
    iterace_celkem: int = 0
    reseedy: int = 0
    log: list[dict] = field(default_factory=list)
    chyby: list[str] = field(default_factory=list)


def faze1a_koncept(klient: OllamaKlient, zadani: Zadani, params: LosovaneParametry) -> Koncept:
    """Architekt navrhne narativní koncept (teorie, řešení, konce) dle archetypu."""
    cile = pocty_cile(zadani)
    prompt = (
        f"Téma: {zadani.tema or '(navrhni sám)'}\n"
        f"Věk: {zadani.vek.value}, formát: {zadani.format_hracu}, "
        f"obtížnost: {zadani.obtiznost.value}, tón: {zadani.ton or '(zvol)'}\n"
        f"Archetyp zvratu: {params.archetyp.value}.\n"
        f"Vyrob koncept: falešných teorií={cile['falesne_teorie']}, "
        f"pravdivých stop≥{cile['pravdive_stopy']}, konců={cile['konce']}. "
        "Pravda se odvozuje průnikem stop, žádný zdroj ji neprozradí."
    )
    data = klient.generuj_json(Role.ARCHITEKT, prompt, SCHEMA_KONCEPT)
    # Počty teorií/stop/konců jsou strukturální omezení (§SKÁLOVÁNÍ) → vlastní je
    # Python, ne LLM: přepiš je na cílové hodnoty (model je občas netrefí).
    data["falesne_teorie"] = cile["falesne_teorie"]
    data["pravdive_stopy"] = cile["pravdive_stopy"]
    data["konce"] = cile["konce"]
    return Koncept.model_validate(data)


def _prompt_architekt(
    zadani: Zadani, koncept: Koncept, params: LosovaneParametry, diagnostiky: list[str],
    predchozi_json: str | None = None,
) -> str:
    n = params.pocet_karet_60
    komp = komponenty_rozsah(60, zadani.obtiznost)
    zaklad = (
        f"Postav mapu hry „{koncept.tema}“ jako ORIENTOVANÝ GRAF {n} uzlů (60min).\n\n"
        "STRUKTURA (kritické): pole `uzly` je seznam uzlů. KAŽDÝ uzel má pole "
        "`hrany` = seznam voleb, kde každá volba je objekt `{\"cil\": <číslo jiného "
        "uzlu>}`. Bez hran je graf nefunkční!\n"
        "Příklad uzlu (JSON):\n"
        '  {"cislo":1,"nazev":"Kraj lesa","typ":"onboarding","region":"les",'
        '"prostredi":"les","profil":"CORE","komponenty":[],"kostka":false,'
        '"klicove_svedectvi":false,"hrany":[{"cil":2},{"cil":3}]}\n\n'
        f"ČÍSLOVÁNÍ: uzly 1..{n}. Uzel 1 = onboarding (START). Poslední uzel = typ "
        "`cil` (má prázdné `hrany`). VŠECHNY ostatní uzly mají ≥1 hranu.\n"
        "SOUVISLOST: z uzlu 1 se musí dát dojít do KAŽDÉHO uzlu; z každého uzlu se "
        "musí dát dojít do cíle (žádný osiřelý uzel, žádný softlock). I gated, "
        "strez a slepé uzly MAJÍ vstupní hrany — zámek je jen podmínka na hraně, "
        "ne chybějící cesta; hráč na ně dojde.\n\n"
        f"TVRDÁ OMEZENÍ:\n"
        f"- archetyp zvratu = {params.archetyp.value}\n"
        f"- prah_aktivity = {params.prah_aktivity}; pozice_aha_uzel = uzel na povinné "
        f"trase kolem {params.pozice_aha_pct:.0f} % cesty (za gated/jednosměrkou)\n"
        f"- typy uzlů (použij přesně tyto řetězce): onboarding, rozcesti, sber, "
        "prechod, slepa, jednosmer, smycka, strez, gated, informace, postava, "
        "lecitel, obchodnik, cil\n"
        f"- POČTY: střežené(strez) 2–3, gated 2, informace ≥3, obchodnik ≥1, "
        f"regiony 2–3, komponenty artefaktu {komp[0]}–{komp[1]} (rozděl je na uzly), "
        f"~30 % uzlů má kostka=true\n"
        f"- TOPOLOGIE: ≥3 uzly s 2+ hranami (rozcestí), ≥2 typ smycka, ≥2 typ slepa "
        "(krátké, vrací zpět), ≥2 jednosměrné (typ jednosmer nebo hrana s "
        '"jednosmerna":true); žádné dvě `sber` hned za sebou\n\n'
        "PROFIL 30/60: každý uzel má profil=CORE nebo SIDE. CORE uzlů je 8–12 a "
        "SAMY tvoří kompletní hratelnou 30min hru — propojené jen přes CORE uzly. "
        "CORE proto MUSÍ samo obsahovat: onboarding (uzel 1), cíl, ≥1 strez, "
        "1 gated, ≥2 informace, ≥1 slepá, ≥2 rozcestí (uzel s 2+ hranami), "
        "≥1 smyčka (typ smycka), obě komponenty artefaktu, klíčová svědectví, "
        "~30 % CORE uzlů s kostka=true, a jen 1–2 regiony. "
        "SIDE uzly (zbytek) jsou vedlejší obohacení jen pro 60min a NEsmí být "
        "jedinou cestou k ničemu povinnému.\n"
        "KLÍČOVÁ SVĚDECTVÍ: označ klicove_svedectvi=true jen u 2–3 uzlů, a to POUZE "
        "na hlavní ose — uzly, kterými projde KAŽDÁ cesta k cíli (typicky hned za "
        "gated podmínkou nebo jednosměrkou). NIKDY na slepé/vedlejší větvi. Stejně "
        "tak pozice_aha_uzel musí ležet na této povinné ose.\n\n"
        "Vrať JEN JSON: archetyp, seed, prah_aktivity, pozice_aha_uzel, regiony, uzly."
    )
    if diagnostiky:
        zaklad += "\n\nOPRAV tyto konkrétní nedostatky předchozí mapy:\n" + "\n".join(
            f"- {d}" for d in diagnostiky[:15]
        )
        if predchozi_json:
            # Inkrementální oprava: nech model minimálně upravit PŘEDCHOZÍ mapu,
            # ať se neopravují chyby regenerací celé mapy (oscilace).
            zaklad += (
                "\n\nToto je tvá PŘEDCHOZÍ mapa. ZACHOVEJ vše ostatní beze změny a "
                "uprav jen to nutné k opravě chyb výše (přidej/uber hranu, přeznač "
                "uzel, přesuň komponentu). NEgeneruj mapu od nuly:\n" + predchozi_json
            )
    return zaklad


def _zavolej_architekta(
    klient: OllamaKlient, zadani: Zadani, koncept: Koncept, params: LosovaneParametry,
    diagnostiky: list[str], predchozi_mapa: Mapa | None = None,
) -> tuple[Mapa | None, str | None]:
    """Jedno volání architekta. Vrací (mapa, None) nebo (None, popis chyby schématu).

    `predchozi_mapa` (poslední naparsovaná mapa) se při opravě přiloží k promptu
    pro inkrementální úpravu místo regenerace od nuly."""
    predchozi_json = predchozi_mapa.model_dump_json() if predchozi_mapa is not None else None
    prompt = _prompt_architekt(zadani, koncept, params, diagnostiky, predchozi_json)
    data = klient.generuj_json(Role.ARCHITEKT, prompt, SCHEMA_MAPA)  # HonbickaLLMError → nahoru
    try:
        return Mapa.model_validate(data), None
    except ValidationError as exc:
        return None, f"mapa nesplňuje schéma ({exc.error_count()} chyb)"


def faze1_architekt(
    klient: OllamaKlient,
    zadani: Zadani,
    koncept: Koncept,
    params: LosovaneParametry,
    *,
    zakazane_archetypy: frozenset[Archetyp] = frozenset(),
    validator: Callable[[Mapa], VysledekValidace] | None = None,
    pocet_simulaci: int = 5,
) -> VysledekFaze1:
    """Opravná smyčka: max 4 iterace, pak relosování seedu (max 2×), pak FAIL.

    `validator` lze injektovat (testy); default validuje pár 30/60 (spec §5)."""
    if validator is None:
        def validator(m: Mapa) -> VysledekValidace:  # noqa: E306
            return validuj_par_30_60(m, zadani, koncept, pocet_simulaci=pocet_simulaci)[0]

    vysledek = VysledekFaze1(ok=False, koncept=koncept, parametry=params)
    akt = params
    for reseed in range(MAX_RELOSOVANI + 1):
        diagnostiky: list[str] = []
        predchozi_mapa: Mapa | None = None  # pro inkrementální opravu (reset po relosování)
        for iterace in range(1, MAX_ITERACI_ARCHITEKT + 1):
            vysledek.iterace_celkem += 1
            mapa, schema_chyba = _zavolej_architekta(
                klient, zadani, koncept, akt, diagnostiky, predchozi_mapa)
            if mapa is None:
                vysledek.log.append({"faze": 1, "reseed": reseed, "iterace": iterace,
                                     "seed": akt.seed, "ok": False, "chyby": [schema_chyba]})
                diagnostiky = [schema_chyba or "neplatná mapa"]
                continue
            predchozi_mapa = mapa  # poslední naparsovaná mapa → základ pro opravu
            v = validator(mapa)
            vysledek.log.append({"faze": 1, "reseed": reseed, "iterace": iterace,
                                 "seed": akt.seed, "ok": v.ok, "chyby": v.chyby})
            if v.ok:
                vysledek.ok = True
                vysledek.mapa = mapa
                vysledek.parametry = akt
                vysledek.reseedy = reseed
                return vysledek
            diagnostiky = v.diagnostika or v.chyby
        if reseed < MAX_RELOSOVANI:
            akt = losuj_parametry(zadani, akt.seed + 1, zakazane_archetypy)
            vysledek.log.append({"faze": 1, "akce": "relosovani", "novy_seed": akt.seed})
    vysledek.reseedy = MAX_RELOSOVANI
    vysledek.chyby = [
        f"FÁZE 1 selhala po {vysledek.iterace_celkem} iteracích a {MAX_RELOSOVANI} relosováních"
    ]
    return vysledek


# --------------------------------------------------------------------------- #
# FÁZE 3 — VYPRAVĚČ (karta po kartě) s okamžitým A5 fit-checkem
# --------------------------------------------------------------------------- #
ATMOSFERA_FLOOR = 200  # pod tuto délku už atmosféru neořezáváme (3.4-7 min 300)


def _potrebuje_30_variantu(mapa: Mapa, uzel: Uzel) -> bool:
    """CORE rozcestník s hranou do SIDE uzlu → dvě varianty zadní strany (spec §5)."""
    if uzel.profil != Profil.CORE:
        return False
    return any(
        (cil := mapa.uzel(h.cil)) is not None and cil.profil == Profil.SIDE
        for h in uzel.hrany
    )


def _kontext_karty(mapa: Mapa, uzel: Uzel) -> dict:
    sousedi = [
        {"cislo": h.cil, "nazev": (c.nazev if (c := mapa.uzel(h.cil)) else "?"),
         "podminka": h.podminka, "side": bool(c and c.profil == Profil.SIDE)}
        for h in uzel.hrany
    ]
    return {
        "sousedi": sousedi,
        "je_aha": uzel.cislo == mapa.pozice_aha_uzel,
        "klicove_svedectvi": uzel.klicove_svedectvi,
    }


def _prompt_vypravec(
    zadani: Zadani, koncept: Koncept, uzel: Uzel, kontext: dict,
    dve_varianty: bool, zkrat_o_pct: int | None, oprava_schematu: bool = False,
) -> str:
    volby = "; ".join(
        f"→{s['cislo']} {s['nazev']}" + (f" [podmínka: {s['podminka']}]" if s["podminka"] else "")
        + (" (SIDE)" if s["side"] else "")
        for s in kontext["sousedi"]
    ) or "(cílová karta — bez voleb)"
    smi = []
    if kontext["je_aha"]:
        smi.append("ZDE padá AHA odhalení — nech hráče poznat pravdu, ale neoznamuj ji přímo")
    if kontext["klicove_svedectvi"]:
        smi.append("nese klíčové svědectví (stopu k pravdě) — podej ho jako výpověď postavy")
    pole = '"nazev", "atmosfera", "predni", "zadni"' + (', "zadni_30"' if dve_varianty else "")
    zaklad = (
        f"Napiš JEDNU kartu č. {uzel.cislo} „{uzel.nazev}“ (typ {uzel.typ.value}).\n"
        f"Téma: {koncept.tema}. Věk: {zadani.vek.value}, tón: {zadani.ton or koncept.zanr}.\n"
        f"Volby (zadní strana): {volby}.\n"
        f"Vrať POUZE JSON s poli {pole}:\n"
        '  "nazev" = název karty; "atmosfera" = atmosférický odstavec 300–500 znaků; '
        '"predni" = příběh + volby (A/B…); "zadni" = výsledky voleb.\n'
        'Příklad: {"nazev":"Kraj lesa","atmosfera":"Mezi kmeny se plazí mlha a čtvrté '
        'světlo kdesi zhaslo…","predni":"Stojíš na kraji lesa. A) k potoku →2  B) na '
        'mýtinu →3","zadni":"A) U potoka najdeš čerstvou stopu. B) Mýtina mlčí."}\n'
        "Atmosférický odstavec (300–500 znaků) je POVINNÝ. Fyzický úkol vždy s příběhovým "
        "důvodem (PROČ). Neúspěšná větev ať baví víc než úspěšná.\n"
    )
    if smi:
        zaklad += "Tato karta: " + "; ".join(smi) + ".\n"
    if dve_varianty:
        zaklad += (
            "Napiš DVĚ varianty zadní strany: `zadni` = plné volby (60min), "
            "`zadni_30` = tytéž volby BEZ karet označených SIDE (30min). Příběh stejný.\n"
        )
    if zkrat_o_pct:
        zaklad += (
            f"\nPŘEDCHOZÍ karta přetekla A5. Zkrať text o ~{zkrat_o_pct} % — "
            "ubírej z atmosférického odstavce, NIKDY z voleb/mechaniky."
        )
    if oprava_schematu:
        zaklad += (
            f"\nPŘEDCHOZÍ odpověď neměla správná pole. Vrať PŘESNĚ pole {pole} "
            "jako plochý JSON objekt (žádné vnořené struktury, žádné 'id')."
        )
    return zaklad


def _normalizuj_kartu(data: dict, uzel: Uzel) -> dict:
    """Srovná drobné odchylky výstupu modelu (id→cislo, doplní typ/nazev)."""
    if not isinstance(data, dict):
        return {}
    if "cislo" not in data:
        data["cislo"] = data.get("id", uzel.cislo)
    data.setdefault("typ", uzel.typ.value)
    data.setdefault("nazev", uzel.nazev)
    return data


def _nouzova_karta(uzel: Uzel, koncept: Koncept) -> Karta:
    """Nouzová karta, když model 3× nevrátí validní obsah — hra se dokončí,
    slabá karta je označena v logu (nikdy neshodí celý balíček, spec §4)."""
    return Karta(
        cislo=uzel.cislo, nazev=uzel.nazev, typ=uzel.typ,
        atmosfera=f"({koncept.tema}) Toto místo skrývá další střípek příběhu; "
                  "rozhlédni se a poskládej, co jsi dosud zjistil.",
        predni="Zvaž, kudy dál, a vyber cestu.", zadni="Cesta pokračuje dál.",
    )


def _orez_atmosfery(karta: Karta, measurer: Measurer) -> list[FitCheck]:
    """Deterministický ořez: zkracuj atmosféru (nikdy mechaniku), dokud přední
    strana nesedne nebo nedosáhne floor. Vrátí finální fit-check."""
    while True:
        fits = fit_check_karty(karta, measurer=measurer)
        if all(f.verdikt for f in fits):
            return fits
        predni_pretece = any(f.strana == "predni" and not f.verdikt for f in fits)
        slova = karta.atmosfera.split()
        if predni_pretece and len(karta.atmosfera) > ATMOSFERA_FLOOR and len(slova) > 5:
            karta.atmosfera = " ".join(slova[:-3]).rstrip(",;:—- ") + "…"
        else:
            return fits  # dál nelze (mechanika přetéká, nebo floor) → fit-check ponechá fail


def napis_kartu(
    klient: OllamaKlient, zadani: Zadani, koncept: Koncept, mapa: Mapa, uzel: Uzel,
    *, measurer: Measurer, log: list[dict] | None = None,
) -> tuple[Karta, list[FitCheck], list[dict]]:
    """Napíše a fit-checkne jednu kartu. Max 3 pokusy o zkrácení přes LLM,
    pak deterministický ořez atmosféry (spec §4 FÁZE 3)."""
    log = log if log is not None else []
    kontext = _kontext_karty(mapa, uzel)
    dve = _potrebuje_30_variantu(mapa, uzel)
    zkrat: int | None = None
    oprava_schematu = False
    karta: Karta | None = None
    fits: list[FitCheck] = []
    for pokus in range(1, MAX_ITERACI_KARTA + 1):
        prompt = _prompt_vypravec(zadani, koncept, uzel, kontext, dve, zkrat, oprava_schematu)
        data = _normalizuj_kartu(klient.generuj_json(Role.VYPRAVEC, prompt, SCHEMA_KARTA), uzel)
        try:
            karta = Karta.model_validate(data)
        except ValidationError as exc:
            oprava_schematu = True  # model nevrátil správná pole → oprav a zkus znovu
            log.append({"faze": 3, "karta": uzel.cislo, "pokus": pokus,
                        "schema_chyba": exc.error_count()})
            continue
        oprava_schematu = False
        karta.cislo, karta.typ = uzel.cislo, uzel.typ  # čísla/typ řídí graf, ne LLM
        if not dve:
            karta.zadni_30 = None
        fits = fit_check_karty(karta, measurer=measurer)
        log.append({"faze": 3, "karta": uzel.cislo, "pokus": pokus,
                    "ok": all(f.verdikt for f in fits)})
        if all(f.verdikt for f in fits):
            return karta, fits, log
        prekroceni = max(
            (f.vyska_mm - f.limit_mm) / f.limit_mm for f in fits if not f.verdikt
        )
        zkrat = max(10, round(prekroceni * 100) + 5)
    if karta is None:  # model 3× nevrátil validní obsah → nouzová karta
        karta = _nouzova_karta(uzel, koncept)
        log.append({"faze": 3, "karta": uzel.cislo, "nouzova_karta": True})
    fits = _orez_atmosfery(karta, measurer)  # deterministický fallback
    log.append({"faze": 3, "karta": uzel.cislo, "orez": "atmosfera",
                "ok": all(f.verdikt for f in fits)})
    return karta, fits, log


def faze3_vypravec(
    klient: OllamaKlient, zadani: Zadani, koncept: Koncept, mapa: Mapa,
    *, measurer: Measurer, log: list[dict] | None = None,
) -> tuple[list[Karta], list[FitCheck], list[dict]]:
    """Napíše všechny karty mapy (v pořadí čísel) s okamžitým fit-checkem."""
    log = log if log is not None else []
    karty: list[Karta] = []
    fit: list[FitCheck] = []
    for uzel in sorted(mapa.uzly, key=lambda u: u.cislo):
        karta, fits, log = napis_kartu(klient, zadani, koncept, mapa, uzel,
                                       measurer=measurer, log=log)
        karty.append(karta)
        fit.extend(fits)
    return karty, fit, log


# --------------------------------------------------------------------------- #
# FÁZE 4 — REDAKTOR (LLM-judge R1–R7 s ověřenými citacemi)
# --------------------------------------------------------------------------- #
REDAKCE_CHECKY: dict[str, str] = {
    "R1": "Pravda se odvozuje průnikem ≥2 nezávislých stop; žádný uzel ji neprozradí.",
    "R2": "Každá falešná teorie má důkazy i jednu nevysvětlenou stopu; vše vysvětlí jen řešení.",
    "R3": "Postavy mají konflikty a protiřečí si; lži plynou z motivací.",
    "R4": "Neúspěšné větve jsou zábavnější než úspěšné (P9).",
    "R5": "Každý fyzický úkol má příběhový důvod (PROČ).",
    "R6": "Jazyk a humor odpovídají věku a tónu.",
    "R7": "Hra nepůsobí jako kopie předchozích (metahra).",
}


def _karty_blob(karty: list[Karta]) -> str:
    return "\n".join(
        f"#{k.cislo} {k.nazev}\n{k.atmosfera}\n{k.predni}\n{k.zadni}\n{k.zadni_30 or ''}"
        for k in karty
    )


# Uvozovky (rovné i české), kterými model citaci obaluje.
_UVOZOVKY = "\"'“”„«»‚‘’"
_PREFIX_CISLA_KARTY = re.compile(r"^#\d+[^:]{0,60}:\s*")
_ELIPSA = re.compile(r"\.\.\.|…")


def _ocisti_citaci(text: str) -> str:
    """Model citaci často obalí uvozovkami a/nebo prefixem „#N Název:" — pro
    ověření proti kartám (`c in blob`) je potřeba čistý úryvek. Přednostně
    vytáhne nejdelší úsek v uvozovkách (ignoruje okolní text i prefix); jinak
    jen odsekne prefix „#N …:" na začátku."""
    t = text.strip()
    m = re.search(r'["“„]([^"“”„]{3,})["”]', t)
    if m:
        return m.group(1).strip()
    return _PREFIX_CISLA_KARTY.sub("", t).strip(_UVOZOVKY).strip()


def _citace_je_dolozena(citace: str, blob: str) -> bool:
    """Ověří citaci proti kartám. Model smí legitimně spojit dva doslovné
    úryvky elipsou („…"/"...") — pak se každý fragment ověří zvlášť (musí jich
    být ≥2 a všechny doslova v kartách); jinak požaduje celý úryvek doslova."""
    text = _ocisti_citaci(citace)
    if not text:
        return False
    if text in blob:
        return True
    fragmenty = [f.strip(" .") for f in _ELIPSA.split(text)]
    fragmenty = [f for f in fragmenty if len(f) >= 3]
    return len(fragmenty) >= 2 and all(f in blob for f in fragmenty)


def faze4_redaktor(
    klient: OllamaKlient, karty: list[Karta], koncept: Koncept, zadani: Zadani
) -> list[RedakceVerdikt]:
    """Projde checky R1–R7. Každý verdikt MUSÍ citovat doslovné úryvky z karet;
    orchestrátor je ověří (grep, po očištění uvozovek/prefixu) — bez existující
    citace je verdikt neplatný (spec §3/§12)."""
    blob = _karty_blob(karty)
    verdikty: list[RedakceVerdikt] = []
    for kod, popis in REDAKCE_CHECKY.items():
        prompt = (
            f"Check {kod}: {popis}\nVěk {zadani.vek.value}, téma „{koncept.tema}“.\n"
            "Posuď karty a doslovně cituj úryvky jako důkaz.\n\n" + blob[:4000]
        )
        try:
            data = klient.generuj_json(Role.REDAKTOR, prompt, SCHEMA_REDAKCE)
            v = RedakceVerdikt.model_validate(data)
        except (HonbickaLLMError, ValidationError) as exc:
            # Posudek je sekundární — chyba/timeout jednoho checku neshodí hru.
            verdikty.append(RedakceVerdikt(
                check=kod, verdikt=False,
                zduvodneni=f"[posudek nedostupný: {type(exc).__name__}]"))
            continue
        v.check = kod
        # Ověření citací: každý úryvek musí být v kartách doslova (příp. jako
        # dva fragmenty spojené elipsou — viz _citace_je_dolozena).
        if not v.citace_karet or not all(_citace_je_dolozena(c, blob) for c in v.citace_karet):
            v.verdikt = False
            v.zduvodneni = (v.zduvodneni + " [citace neověřena]").strip()
        verdikty.append(v)
    return verdikty


# --------------------------------------------------------------------------- #
# FÁZE 5 — zápis skinu, sazba PDF, registr, taxonomie
# --------------------------------------------------------------------------- #
def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "hra"


def _koncept_md(koncept: Koncept, params: LosovaneParametry) -> str:
    return (
        f"# Koncept — {koncept.tema}\n\n"
        f"- Archetyp: {koncept.archetyp.value}\n"
        f"- Mechanismus řešení: {koncept.mechanismus_reseni}\n"
        f"- Klíčová rekvizita: {koncept.klicova_rekvizita}\n"
        f"- Falešné teorie / pravdivé stopy / konce: "
        f"{koncept.falesne_teorie} / {koncept.pravdive_stopy} / {koncept.konce}\n"
        f"- Seed: {params.seed} · práh: {params.prah_aktivity} · "
        f"pozice AHA cíl: {params.pozice_aha_pct:.0f} %\n"
    )


def _zapis_skin(hra_dir: str, koncept_md: str, mapa: Mapa | None,
                karty: list[Karta], report: Report, log: list[dict]) -> None:
    os.makedirs(hra_dir, exist_ok=True)

    def _w(nazev: str, obsah: str) -> None:
        with open(os.path.join(hra_dir, nazev), "w", encoding="utf-8") as f:
            f.write(obsah)

    _w("koncept.md", koncept_md)
    if mapa is not None:
        _w("mapa.json", mapa.model_dump_json(indent=2))
    _w("karty.json", json.dumps([k.model_dump() for k in karty], ensure_ascii=False, indent=2))
    _w("report.json", report.model_dump_json(indent=2))
    _w("log.jsonl", "\n".join(json.dumps(e, ensure_ascii=False) for e in log))


def _pdf_sady(
    hra_dir: str, zadani: Zadani, koncept: Koncept, params: LosovaneParametry,
    mapa: Mapa, karty: list[Karta], editorial: list[RedakceVerdikt],
) -> bool:
    """Vyrenderuje všechny PDF (karty 30/60, herní listy, průvodce). Bez GTK
    vrátí False (SazbaNedostupna) — hra zůstává datově platná."""
    core_cisla = {u.cislo for u in mapa.core_uzly}
    core_karty = [k for k in karty if k.cislo in core_cisla]
    komponenty = len({c for u in mapa.uzly for c in u.komponenty}) or 2
    try:
        uloz_pdf_karet(karty, os.path.join(hra_dir, "karty_60min.pdf"),
                       nadpis=koncept.tema, zadni_strana="zadni")
        uloz_pdf_karet(core_karty, os.path.join(hra_dir, "karty_30min.pdf"),
                       nadpis=koncept.tema, zadni_strana="zadni_30")
        for profil, komp in ((60, komponenty), (30, 2)):
            hl = postav_html_herni_list(
                tema=koncept.tema, prah=params.prah_aktivity, profil_min=profil,
                format_hracu=zadani.format_hracu, pocet_komponent=komp,
                je_volny_format=zadani.je_volny_format,
            )
            zapis_pdf(hl, os.path.join(hra_dir, f"herni_list_{profil}min.pdf"))
        for profil, sada in ((60, karty), (30, core_karty)):
            pr = postav_html_pruvodce(koncept=koncept, zadani=zadani, mapa=mapa,
                                      karty=sada, prah=params.prah_aktivity,
                                      editorial=editorial)
            zapis_pdf(pr, os.path.join(hra_dir, f"pruvodce_{profil}min.pdf"))
        return True
    except SazbaNedostupna:
        return False


# --------------------------------------------------------------------------- #
# Celý stavový stroj (FÁZE 0–5)
# --------------------------------------------------------------------------- #
def vyrob_hru(
    zadani: Zadani,
    klient: OllamaKlient,
    *,
    seed: int | None = None,
    measurer: Measurer | None = None,
    skiny_dir: str = "skiny",
    registr_cesta: str = "skiny/registr.md",
    zatridit: bool = True,
    pouzij_scaffolder: bool = True,
) -> Hra:
    """Provede jednu hru celým stavovým strojem FÁZE 0–5 (spec §4).

    `pouzij_scaffolder=True` (default): FÁZE 1 staví mapu deterministicky
    (`scaffold.postav_skeleton`) — spolehlivé a okamžité. False = legacy LLM
    architekt s opravnou smyčkou (nekonverguje spolehlivě, viz docs/rozhodnuti.md).

    `measurer` default = reálný WeasyPrint (vyžaduje GTK); testy dodají fake.
    PDF krok bez GTK selže měkce (report.chyby), hra zůstane datově platná.
    """
    measurer = measurer or _weasy_measurer
    seed = seed if seed is not None else random.randint(1, 10**9)
    log: list[dict] = []

    # FÁZE 0 — registr → okna zákazů → losování
    zaznamy = nacti_registr(registr_cesta)
    zakazane = zakazane_archetypy(zaznamy)
    params = losuj_parametry(zadani, seed, zakazane)
    log.append({"faze": 0, "seed": seed, "archetyp": params.archetyp.value,
                "prah": params.prah_aktivity, "zakazane": sorted(a.value for a in zakazane)})

    # FÁZE 1a — koncept
    koncept = faze1a_koncept(klient, zadani, params)
    if not koncept.tema:
        koncept.tema = zadani.tema or f"hra-{seed}"
    slug = _slug(koncept.tema)
    hra_dir = os.path.join(skiny_dir, slug)

    # FÁZE 1b — mapa: deterministický scaffolder (default) nebo LLM architekt
    if pouzij_scaffolder:
        from honbicka.scaffold import POCET_SIMULACI, postav_skeleton
        mapa = postav_skeleton(zadani, koncept, params)
        v_mapa, _ = validuj_par_30_60(mapa, zadani, koncept, pocet_simulaci=POCET_SIMULACI)
        log.append({"faze": 1, "scaffolder": True, "ok": v_mapa.ok, "chyby": v_mapa.chyby,
                    "aha_uzel": mapa.pozice_aha_uzel})
        if not v_mapa.ok:  # nemělo by nastat (validní z konstrukce)
            report = Report(slug=slug, seed=seed, archetyp=params.archetyp, iterace=1,
                            stav=StavHry.FAILED, chyby=["scaffolder: " + c for c in v_mapa.chyby])
            _zapis_skin(hra_dir, _koncept_md(koncept, params), None, [], report, log)
            return Hra(slug=slug, zadani=zadani, koncept=_koncept_md(koncept, params),
                       mapa=None, karty=[], report=report)
        iterace_faze1 = 1
    else:
        f1 = faze1_architekt(klient, zadani, koncept, params, zakazane_archetypy=zakazane)
        log.extend(f1.log)
        if not f1.ok or f1.mapa is None:
            report = Report(slug=slug, seed=seed, archetyp=params.archetyp,
                            iterace=f1.iterace_celkem, stav=StavHry.FAILED, chyby=f1.chyby)
            _zapis_skin(hra_dir, _koncept_md(koncept, params), None, [], report, log)
            return Hra(slug=slug, zadani=zadani, koncept=_koncept_md(koncept, params),
                       mapa=None, karty=[], report=report)
        mapa = f1.mapa
        iterace_faze1 = f1.iterace_celkem

    # FÁZE 3 — vypravěč karta po kartě + A5 fit-check
    karty, fit, log = faze3_vypravec(klient, zadani, koncept, mapa, measurer=measurer, log=log)

    # Průběžný zápis: koncept/mapa/karty se uloží HNED po FÁZE 3, ať drahou
    # generaci nezahodí případný pád redaktora/sazby (spec §4 — jedna vada balíček nešhodí).
    predbezny = Report(slug=slug, seed=seed, archetyp=params.archetyp, iterace=iterace_faze1,
                       stav=StavHry.OK, fit_check=fit)
    _zapis_skin(hra_dir, _koncept_md(koncept, params), mapa, karty, predbezny, log)

    # FÁZE 4 — redaktor R1–R7 s ověřenými citacemi (resilientní: chyba neshodí hru)
    editorial = faze4_redaktor(klient, karty, koncept, zadani)

    # simulace pro report
    _, sim_mapa = validuj_par_30_60(mapa, zadani, koncept)
    sim_reports = sim_mapa["60"] + sim_mapa["30"]

    chyby: list[str] = []
    if any(not f.verdikt for f in fit):
        chyby.append("některé karty nesedí na A5 (fit-check)")
    if any(not v.verdikt for v in editorial):
        chyby.append("redakční posudek našel nedostatky (viz editorial_report)")

    report = Report(
        slug=slug, seed=seed, archetyp=params.archetyp, iterace=iterace_faze1,
        stav=StavHry.OK, editorial_report=editorial, simulation_reports=sim_reports,
        fit_check=fit, chyby=chyby,
        validation_report={"karet": len(karty), "core_karet": len(mapa.core_uzly)},
    )

    # FÁZE 5 — zápis skinu + sazba + registr + taxonomie
    _zapis_skin(hra_dir, _koncept_md(koncept, params), mapa, karty, report, log)
    pdf_ok = _pdf_sady(hra_dir, zadani, koncept, params, mapa, karty, editorial)
    if not pdf_ok:
        report.chyby.append("PDF nevyrenderováno (GTK/WeasyPrint chybí)")
        _zapis_skin(hra_dir, _koncept_md(koncept, params), mapa, karty, report, log)

    zapis_zaznam(ZaznamRegistru(
        datum=date.today().isoformat(), slug=slug, archetyp=params.archetyp.value,
        mechanismus=koncept.mechanismus_reseni, rekvizity=koncept.klicova_rekvizita,
        zanr_publikum=f"{koncept.zanr}/{zadani.vek.value}", profily="30+60", seed=seed,
    ), registr_cesta)

    if zatridit:
        zatrid_hru(zadani, slug, hra_dir)

    return Hra(slug=slug, zadani=zadani, koncept=_koncept_md(koncept, params),
               mapa=mapa, karty=karty, report=report)
