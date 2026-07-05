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
    SCHEMA_REDAKCE_VSECHNY,
    SCHEMA_ZADANI,
    Archetyp,
    FitCheck,
    Hra,
    Hrana,
    Karta,
    Koncept,
    Mapa,
    Profil,
    RedakceVerdikt,
    RedakceVsechnyVerdikty,
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
from honbicka.sazba.render import SazbaNedostupna, je_dostupne, zapis_pdf
from honbicka.taxonomie import zatrid_hru
from honbicka.validatory import VysledekValidace
from honbicka.validatory.agregace import validuj_par_30_60
from honbicka.validatory.sazba import Measurer, _weasy_measurer, fit_check_karty
from honbicka.validatory.simulace import pasmo_aha
from honbicka.validatory.skalovani import SKALA, VEK_STROP, komponenty_rozsah

MAX_ITERACI_ARCHITEKT = 4  # spec §4 FÁZE 1
MAX_RELOSOVANI = 2  # spec §4 FÁZE 1
MAX_ITERACI_KARTA = 3  # spec §4 FÁZE 3
MAX_ITERACI_KONCEPT = 3  # O5: opravný pokus, když mechanismus_reseni/rekvizita nevyhoví

# Váhy archetypů (SKILL.md §P0b). Losuje Python.
ARCHETYP_VAHY: dict[Archetyp, int] = {
    Archetyp.A1: 30, Archetyp.A2: 15, Archetyp.A3: 12, Archetyp.A4: 12,
    Archetyp.A5: 10, Archetyp.A6: 9, Archetyp.A7: 12,
}


# --------------------------------------------------------------------------- #
# TÉMA-GENERÁTOR (auto režim, spec §3.1) — thinking OFF, temp 1.0
# --------------------------------------------------------------------------- #
def vygeneruj_tema(
    klient: OllamaKlient,
    vek: VekPasmo,
    format_hracu: str,
    zaznamy: list[ZaznamRegistru],
    feedbacky: list[str] | None = None,
) -> Zadani:
    """Navrhne téma/žánr/prostředí/tón lišící se od posledních 10 her (spec §3.1).

    Věk a formát řídí plán (ne LLM) — vloží se PŘED validací, protože model je
    nemusí vrátit vůbec (`vek` je na `Zadani` povinné pole) nebo správně (i se
    structured outputem). Nepoužívá se tu `generuj_model` (L1): to by validovalo
    RAW odpověď modelu ještě před přepsáním vek/format_hracu, takže by chybějící
    `vek` shodil retry smyčku zbytečně — potřebujeme nejdřív dict opravit, pak
    validovat. Enum obtížnosti normalizuje přímo `Zadani` (model vrací i
    diakritiku — viz `_normalizuj_obtiznost` validator na modelu)."""
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
    # Plán je autoritativní pro věk/formát bez ohledu na to, co (ne)vrátil model.
    data["vek"] = vek.value
    data["format_hracu"] = format_hracu
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


def _normalizuj_koncept_data(data: dict) -> dict:
    """Mechanická poslední záchrana (O5), když model po vyčerpání opravných
    pokusů pořád vrací snake_case token místo věty: nahradí podtržítka
    mezerami a doplní generický zbytek, ať `Koncept.model_validate` neselže
    na kosmeticky vadném poli. Hru to nikdy nemá shodit."""
    m = data.get("mechanismus_reseni")
    if isinstance(m, str):
        t = m.replace("_", " ").strip()
        if not t:
            t = "Pravda se skládá z nezávislých stop, ne z jednoho zdroje."
        elif " " not in t or len(t) < 15:
            t = f"{t} — vysvětlí se během hraní."
        data["mechanismus_reseni"] = t
    r = data.get("klicova_rekvizita")
    if isinstance(r, str):
        data["klicova_rekvizita"] = r.replace("_", " ").strip()
    return data


def faze1a_koncept(klient: OllamaKlient, zadani: Zadani, params: LosovaneParametry) -> Koncept:
    """Architekt navrhne narativní koncept (teorie, řešení, konce) dle archetypu.

    O5: `mechanismus_reseni`/`klicova_rekvizita` musí být plné věty/fráze
    (viz `Koncept` validátory), ne snake_case tokeny — jinak jsou okna zákazů
    v registru bezcenná (R1). Při nevalidním poli se zopakuje s cíleným
    opravným promptem; po vyčerpání pokusů mechanická oprava (O5)."""
    cile = pocty_cile(zadani)
    prompt = (
        f"Téma: {zadani.tema or '(navrhni sám)'}\n"
        f"Věk: {zadani.vek.value}, formát: {zadani.format_hracu}, "
        f"obtížnost: {zadani.obtiznost.value}, tón: {zadani.ton or '(zvol)'}\n"
        f"Archetyp zvratu: {params.archetyp.value}.\n"
        f"Vyrob koncept: falešných teorií={cile['falesne_teorie']}, "
        f"pravdivých stop≥{cile['pravdive_stopy']}, konců={cile['konce']}. "
        "Pravda se odvozuje průnikem stop, žádný zdroj ji neprozradí.\n"
        "KRITICKÉ: `mechanismus_reseni` MUSÍ být celá věta popisující, jak se "
        "pravda doopravdy odvodí (ne jednoslovný token spojený podtržítky). "
        "`klicova_rekvizita` je krátká fráze (smí být i jedno slovo), ale bez "
        "podtržítek.\n"
        'Příklad DOBŘE: {"mechanismus_reseni":"Drak kýchá kvůli pylu z jediné '
        'vzácné květiny na louce","klicova_rekvizita":"vzácná květina"}\n'
        'Příklad ŠPATNĚ (NEDĚLAT): {"mechanismus_reseni":"drak_kyha_pyl",'
        '"klicova_rekvizita":"kvetina_louka"}'
    )
    data: dict = {}
    posledni_chyba = ""
    for pokus in range(1, MAX_ITERACI_KONCEPT + 1):
        data = klient.generuj_json(Role.ARCHITEKT, prompt, SCHEMA_KONCEPT)
        # Počty teorií/stop/konců jsou strukturální omezení (§SKÁLOVÁNÍ) → vlastní
        # je Python, ne LLM: přepiš je na cílové hodnoty (model je občas netrefí).
        data["falesne_teorie"] = cile["falesne_teorie"]
        data["pravdive_stopy"] = cile["pravdive_stopy"]
        data["konce"] = cile["konce"]
        try:
            return Koncept.model_validate(data)
        except ValidationError as exc:
            posledni_chyba = str(exc)
            if pokus < MAX_ITERACI_KONCEPT:
                prompt += (
                    f"\nPŘEDCHOZÍ odpověď nevyhověla ({exc.error_count()} chyb): "
                    "mechanismus_reseni MUSÍ být celá věta se slovy oddělenými "
                    "mezerou (ne token spojený podtržítky), klicova_rekvizita bez "
                    "podtržítek. Zkus to znovu."
                )
    # Vyčerpáno → mechanická oprava (nikdy nespadnout jen na kosmetickém poli).
    try:
        return Koncept.model_validate(_normalizuj_koncept_data(data))
    except ValidationError as exc:
        # Selhalo i jiné pole než mechanismus/rekvizita (schéma je jinak vadné) —
        # to mechanická oprava neřeší, hra to zachytí jako FAILED FÁZE 1.
        raise RuntimeError(
            f"koncept: nevalidní i po {MAX_ITERACI_KONCEPT} pokusech a mechanické "
            f"opravě ({posledni_chyba})"
        ) from exc


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
        # Heuristika (O3): čísla uzlů zhruba sledují pořadí trunku, takže nižší
        # číslo než AHA uzel = karta se hraje dřív. Není to grafově přesné
        # (větve/SIDE smyčky), jen orientační signál pro vypravěče.
        "pred_aha": uzel.cislo < mapa.pozice_aha_uzel,
    }


def _prompt_vypravec(
    zadani: Zadani, koncept: Koncept, uzel: Uzel, kontext: dict,
    dve_varianty: bool, zkrat_o_pct: int | None, oprava_schematu: bool = False,
    oprava_voleb: bool = False,
) -> str:
    volby = "; ".join(
        f"→{s['cislo']} {s['nazev']}" + (f" [podmínka: {s['podminka']}]" if s["podminka"] else "")
        + (" (SIDE)" if s["side"] else "")
        for s in kontext["sousedi"]
    ) or "(cílová karta — bez voleb)"
    cisla = sorted({s["cislo"] for s in kontext["sousedi"]})
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
    # O3: kontext zápletky pro narativní soudržnost napříč kartami — pravda se
    # NIKDY neoznamuje přímo (SKILL.md P0), tohle je jen skryté pozadí příběhu,
    # ať karty ladí (stejné motivy, rekvizity, postavy), ne aby se citovalo.
    zaklad += (
        f"\nSKRYTÉ POZADÍ PŘÍBĚHU (pro soudržnost — NIKDY neprozraď přímo, ani "
        f"náznakem mimo AHA kartu): skutečné řešení je „{koncept.mechanismus_reseni}“; "
        f"klíčová rekvizita příběhu: „{koncept.klicova_rekvizita or koncept.tema}“.\n"
    )
    if not kontext["je_aha"]:
        if kontext["pred_aha"]:
            zaklad += (
                "Tato karta je PŘED odhalením — hráč pravdu ještě nezná, smíš jen "
                "nenápadně naznačovat (barvy, předměty, chování postav), nikdy potvrdit.\n"
            )
        else:
            zaklad += (
                "Tato karta je PO odhalení — hráč už pravdu zná, text na ni může "
                "navazovat (dozvuky, reakce postav), ale nemusí ji opakovat.\n"
            )
    if cisla:
        zaklad += (
            f"KRITICKÉ: čísla za šipkou (→) v `predni` i `zadni` MUSÍ být PŘESNĚ "
            f"z množiny {cisla} — žádná jiná, a nikdy číslo této karty ({uzel.cislo}).\n"
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
    if oprava_voleb:
        zaklad += (
            f"\nPŘEDCHOZÍ karta odkazovala na ŠPATNÁ čísla za šipkou (→). Volby MUSÍ "
            f"vést PŘESNĚ na čísla {cisla} — zkontroluj a oprav VŠECHNY šipky."
        )
    return zaklad


# Regex „→ N" (číslo volby v textu karty) — pro ověření proti hranám grafu (O1).
_SIPKA_CISLO = re.compile(r"→\s*(\d+)")


def _extrahuj_cisla_voleb(text: str) -> set[int]:
    return {int(n) for n in _SIPKA_CISLO.findall(text)}


def _ocekavana_cisla_voleb(mapa: Mapa, uzel: Uzel, *, jen_core: bool = False) -> set[int]:
    """Platná cílová čísla pro tento uzel. `jen_core=True` (varianta zadni_30)
    vyloučí cíle typu SIDE — ty se v 30min variantě nesmí objevit (spec §5)."""
    cile = {h.cil for h in uzel.hrany}
    if not jen_core:
        return cile
    return {c for c in cile if (u := mapa.uzel(c)) is None or u.profil != Profil.SIDE}


def _volby_v_karte_platne(karta: Karta, uzel: Uzel, mapa: Mapa) -> bool:
    """Ověří, že každé „→N" v textu karty odpovídá skutečné hraně grafu (O1) —
    bez toho by vytištěná karta mohla poslat hráče na špatnou/neexistující kartu."""
    ocekavana = _ocekavana_cisla_voleb(mapa, uzel)
    if not ocekavana:
        return True  # cílová karta / uzel bez hran — nic k ověření

    def _shoduje(text: str, platna: set[int]) -> bool:
        nalezena = _extrahuj_cisla_voleb(text)
        return bool(nalezena) and nalezena <= platna

    if not _shoduje(karta.predni, ocekavana) or not _shoduje(karta.zadni, ocekavana):
        return False
    if karta.zadni_30:
        ocekavana_core = _ocekavana_cisla_voleb(mapa, uzel, jen_core=True)
        if not _shoduje(karta.zadni_30, ocekavana_core):
            return False
    return True


def _oprav_volby_deterministicky(karta: Karta, uzel: Uzel, mapa: Mapa) -> Karta:
    """Poslední záchrana po vyčerpání opravných promptů: má-li uzel jediný
    platný cíl, jednoznačně přepíše všechna „→N" na správné číslo (bezpečné —
    není co zaměnit). Víc cílů = nejednoznačná oprava, ponechá se beze změny
    (zavolávající kód to zaznamená do logu/report.chyby)."""
    ocekavana = _ocekavana_cisla_voleb(mapa, uzel)
    if len(ocekavana) == 1:
        cil = next(iter(ocekavana))
        nahrada = rf"→{cil}"
        karta.predni = _SIPKA_CISLO.sub(nahrada, karta.predni)
        karta.zadni = _SIPKA_CISLO.sub(nahrada, karta.zadni)
        if karta.zadni_30:
            karta.zadni_30 = _SIPKA_CISLO.sub(nahrada, karta.zadni_30)
    return karta


def _normalizuj_kartu(data: dict, uzel: Uzel) -> dict:
    """Srovná drobné odchylky výstupu modelu (id→cislo, doplní typ/nazev)."""
    if not isinstance(data, dict):
        return {}
    if "cislo" not in data:
        data["cislo"] = data.get("id", uzel.cislo)
    data.setdefault("typ", uzel.typ.value)
    data.setdefault("nazev", uzel.nazev)
    return data


_PISMENA_VOLEB = "ABCDEFGH"


def _nouzove_volby(hrany: list[Hrana]) -> str:
    """Bezpečné volby „A) Pokračuj → N" z hran uzlu (O6) — bez nich by
    nouzová karta neměla žádnou platnou navigaci a rozbila by hru."""
    if not hrany:
        return "Příběh na této kartě končí."
    return "  ".join(
        f"{_PISMENA_VOLEB[i] if i < len(_PISMENA_VOLEB) else i + 1}) Pokračuj → {h.cil}"
        for i, h in enumerate(hrany)
    )


def _nouzova_karta(uzel: Uzel, koncept: Koncept, mapa: Mapa) -> Karta:
    """Nouzová karta, když model 3× nevrátí validní obsah — hra se dokončí,
    slabá karta je označena v logu (nikdy neshodí celý balíček, spec §4).
    Volby (O6) se generují přímo z hran grafu, takže vždy odpovídají mapě
    (na rozdíl od LLM textu je není třeba ověřovat přes _volby_v_karte_platne)."""
    karta = Karta(
        cislo=uzel.cislo, nazev=uzel.nazev, typ=uzel.typ,
        atmosfera=f"({koncept.tema}) Toto místo skrývá další střípek příběhu; "
                  "rozhlédni se a poskládej, co jsi dosud zjistil.",
        predni=f"Zvaž, kudy dál. {_nouzove_volby(uzel.hrany)}",
        zadni=f"Cesta pokračuje. {_nouzove_volby(uzel.hrany)}",
    )
    if _potrebuje_30_variantu(mapa, uzel):
        hrany_core = [
            h for h in uzel.hrany
            if (c := mapa.uzel(h.cil)) is None or c.profil != Profil.SIDE
        ]
        karta.zadni_30 = f"Cesta pokračuje. {_nouzove_volby(hrany_core)}"
    return karta


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
    """Napíše a fit-checkne jednu kartu. Max 3 pokusy o opravu (schéma, volby
    ↔ hrany grafu — O1, zkrácení) přes LLM, pak deterministický fallback
    (spec §4 FÁZE 3). Volby v textu MUSÍ odpovídat skutečným hranám uzlu —
    jinak by vytištěná karta posílala hráče na špatné/neexistující číslo."""
    log = log if log is not None else []
    kontext = _kontext_karty(mapa, uzel)
    dve = _potrebuje_30_variantu(mapa, uzel)
    zkrat: int | None = None
    oprava_schematu = False
    oprava_voleb = False
    karta: Karta | None = None
    fits: list[FitCheck] = []
    for pokus in range(1, MAX_ITERACI_KARTA + 1):
        prompt = _prompt_vypravec(zadani, koncept, uzel, kontext, dve, zkrat,
                                  oprava_schematu, oprava_voleb)
        data = _normalizuj_kartu(klient.generuj_json(Role.VYPRAVEC, prompt, SCHEMA_KARTA), uzel)
        try:
            karta = Karta.model_validate(data)
        except ValidationError as exc:
            oprava_schematu = True  # model nevrátil správná pole → oprav a zkus znovu
            oprava_voleb = False
            log.append({"faze": 3, "karta": uzel.cislo, "pokus": pokus,
                        "schema_chyba": exc.error_count()})
            continue
        oprava_schematu = False
        karta.cislo, karta.typ = uzel.cislo, uzel.typ  # čísla/typ řídí graf, ne LLM
        if not dve:
            karta.zadni_30 = None

        if not _volby_v_karte_platne(karta, uzel, mapa):
            oprava_voleb = True  # „→N" v textu neodpovídá hranám grafu (O1) → oprav
            log.append({"faze": 3, "karta": uzel.cislo, "pokus": pokus, "volby_chyba": True})
            continue
        oprava_voleb = False

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
        karta = _nouzova_karta(uzel, koncept, mapa)
        log.append({"faze": 3, "karta": uzel.cislo, "nouzova_karta": True})
    elif not _volby_v_karte_platne(karta, uzel, mapa):
        # Poslední pokus měl validní obsah, ale volby stále neodpovídají grafu.
        karta = _oprav_volby_deterministicky(karta, uzel, mapa)
        if _volby_v_karte_platne(karta, uzel, mapa):
            log.append({"faze": 3, "karta": uzel.cislo, "volby_opraveny_deterministicky": True})
        else:
            # Víc než 1 platný cíl = nejednoznačná oprava; zaznamenat pro report.chyby.
            log.append({"faze": 3, "karta": uzel.cislo, "volby_neopravitelne": True})
    fits = _orez_atmosfery(karta, measurer)  # deterministický fallback
    log.append({"faze": 3, "karta": uzel.cislo, "orez": "atmosfera",
                "ok": all(f.verdikt for f in fits)})
    return karta, fits, log


def _synchronizuj_nazvy_uzlu(mapa: Mapa, karty: list[Karta]) -> None:
    """SC3: vypravěč si pro každou kartu vymyslí vlastní název (žádoucí —
    scaffolder dává jen generické 'prechod 10'). Beze změny by ale tenhle
    generický název skončil v průvodci (Rozmístění uzlů) a organizátor by na
    značce viděl jiný název, než je na kartě, kterou tam najde (živě ověřeno:
    karta „Čtyři světla" 3×). Propíše `karta.nazev` zpět do `mapa.uzly[].nazev`
    — deterministicky, žádné nové LLM volání. Duplicitní názvy (dva uzly se
    stejným nápadem vypravěče) rozliší číslem uzlu, ať zůstanou jedinečné pro
    signage."""
    videne: set[str] = set()
    for karta in sorted(karty, key=lambda k: k.cislo):
        uzel = mapa.uzel(karta.cislo)
        if uzel is None:
            continue
        nazev = karta.nazev
        if nazev in videne:
            nazev = f"{nazev} ({karta.cislo})"
        videne.add(nazev)
        uzel.nazev = nazev


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
    _synchronizuj_nazvy_uzlu(mapa, karty)
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


def _vzorkuj_karty_pro_redakci(
    karty: list[Karta], mapa: Mapa | None, *, pocet_nahodnych: int = 4
) -> list[Karta]:
    """O2: redaktor dřív viděl jen `blob[:4000]` (~4 z 21 karet, slepě
    oříznuté uprostřed karty). Místo prefixu vzorkuje CELÉ karty: AHA kartu +
    karty s klíčovým svědectvím + N náhodných (seedováno `mapa.seed` —
    deterministické). Bez `mapa` (test/legacy volání) vrátí všechny karty."""
    if mapa is None:
        return karty
    dulezita_cisla = {mapa.pozice_aha_uzel} | {u.cislo for u in mapa.uzly if u.klicove_svedectvi}
    vybrane = [k for k in karty if k.cislo in dulezita_cisla]
    zbyle = [k for k in karty if k.cislo not in dulezita_cisla]
    rng = random.Random(mapa.seed)
    nahodne = rng.sample(zbyle, min(pocet_nahodnych, len(zbyle)))
    vysledek = vybrane + nahodne
    vysledek.sort(key=lambda k: k.cislo)
    return vysledek


def _faze4_redaktor_po_jednom(
    klient: OllamaKlient, blob: str, koncept: Koncept, zadani: Zadani
) -> list[RedakceVerdikt]:
    """Záložní cesta (L7): 7 sekvenčních volání, jedno na check — použije se,
    jen když jedno sloučené volání (`faze4_redaktor`) selže."""
    verdikty: list[RedakceVerdikt] = []
    for kod, popis in REDAKCE_CHECKY.items():
        prompt = (
            f"Check {kod}: {popis}\nVěk {zadani.vek.value}, téma „{koncept.tema}“. "
            f"Skutečné řešení: „{koncept.mechanismus_reseni}“.\n"
            "Posuď karty a doslovně cituj úryvky jako důkaz.\n\n" + blob
        )
        try:
            data = klient.generuj_json(Role.REDAKTOR, prompt, SCHEMA_REDAKCE)
            v = RedakceVerdikt.model_validate(data)
            v.check = kod
        except (HonbickaLLMError, ValidationError) as exc:
            # Posudek je sekundární — chyba/timeout jednoho checku neshodí hru.
            v = RedakceVerdikt(check=kod, verdikt=False,
                               zduvodneni=f"[posudek nedostupný: {type(exc).__name__}]")
        verdikty.append(v)
    return verdikty


def faze4_redaktor(
    klient: OllamaKlient, karty: list[Karta], koncept: Koncept, zadani: Zadani,
    mapa: Mapa | None = None,
) -> list[RedakceVerdikt]:
    """FÁZE 4: JEDNO volání se všemi checky R1–R7 najednou (L7/O13 — dřív 7
    sekvenčních thinking-ON volání trvalo v živém běhu ~15 min a často
    timeoutovalo). Vzorkuje celé karty místo oříznutého prefixu (O2, viz
    `_vzorkuj_karty_pro_redakci`). Selže-li sloučené volání, spadne na
    záložní cestu po jednom checku (`_faze4_redaktor_po_jednom`). Každý
    verdikt MUSÍ citovat doslovné úryvky z karet; orchestrátor je ověří
    (grep, po očištění uvozovek/prefixu) — bez existující citace je verdikt
    neplatný (spec §3/§12)."""
    vzorek = _vzorkuj_karty_pro_redakci(karty, mapa)
    blob = _karty_blob(vzorek)
    checky_popis = "\n".join(f"{kod}: {popis}" for kod, popis in REDAKCE_CHECKY.items())
    prompt = (
        f"Posuď VŠECH 7 checků najednou pro tuto hru. Téma „{koncept.tema}“, "
        f"věk {zadani.vek.value}. Skutečné řešení: „{koncept.mechanismus_reseni}“.\n\n"
        f"{checky_popis}\n\n"
        f"Karty (vzorek {len(vzorek)} z {len(karty)}):\n{blob}\n\n"
        "Vrať pole `verdikty` s PŘESNĚ 7 položkami (check R1 až R7), každá s "
        "doslovnou citací z karet jako důkaz."
    )
    try:
        data = klient.generuj_json(Role.REDAKTOR, prompt, SCHEMA_REDAKCE_VSECHNY)
        verdikty = RedakceVsechnyVerdikty.model_validate(data).verdikty
    except Exception:  # noqa: BLE001 — jedno volání selhává celé; nikdy nespadnout na FÁZI 4
        verdikty = _faze4_redaktor_po_jednom(klient, blob, koncept, zadani)

    # Model nemusí vrátit přesně 7 položek — chybějící checky = FAILED.
    ziskane = {v.check for v in verdikty}
    for kod in REDAKCE_CHECKY:
        if kod not in ziskane:
            verdikty.append(RedakceVerdikt(check=kod, verdikt=False,
                                           zduvodneni="[chybí v odpovědi redaktora]"))

    vysledek: list[RedakceVerdikt] = []
    for v in verdikty:
        # Ověření citací: každý úryvek musí být v kartách doslova (příp. jako
        # dva fragmenty spojené elipsou — viz _citace_je_dolozena).
        if not v.citace_karet or not all(_citace_je_dolozena(c, blob) for c in v.citace_karet):
            v.verdikt = False
            v.zduvodneni = (v.zduvodneni + " [citace neověřena]").strip()
        vysledek.append(v)
    return vysledek


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
    Bez GTK a bez vlastního `measurer` (C1) hra FAIL-FASTuje HNED po FÁZE 0 —
    PŘED prvním (drahým) voláním LLM — místo pádu uprostřed FÁZE 3. PDF krok
    (FÁZE 5) bez GTK selže měkce (report.chyby), hra zůstane datově platná.
    """
    pouziva_vychozi_measurer = measurer is None
    measurer = measurer or _weasy_measurer
    seed = seed if seed is not None else random.randint(1, 10**9)
    log: list[dict] = []

    # FÁZE 0 — registr → okna zákazů → losování (bez LLM, bez GTK)
    zaznamy = nacti_registr(registr_cesta)
    zakazane = zakazane_archetypy(zaznamy)
    params = losuj_parametry(zadani, seed, zakazane)
    log.append({"faze": 0, "seed": seed, "archetyp": params.archetyp.value,
                "prah": params.prah_aktivity, "zakazane": sorted(a.value for a in zakazane)})

    # Fail-fast (C1): bez GTK by fit-check/PDF stejně spadl, ale AŽ po
    # zaplacení drahé LLM generace (koncept + karty). Zjisti to HNED.
    if pouziva_vychozi_measurer and not je_dostupne():
        slug = _slug(zadani.tema or f"hra-{seed}")
        chyba = (
            "GTK/WeasyPrint není dostupné — A5 fit-check i PDF renderování by "
            "selhaly až po drahé LLM generaci. Nainstaluj GTK runtime (viz README, "
            "proměnná HONBICKA_GTK_DIR) nebo předej vlastní `measurer`."
        )
        log.append({"faze": 0, "akce": "fail_fast_gtk", "chyba": chyba})
        report = Report(slug=slug, seed=seed, archetyp=params.archetyp, iterace=0,
                        stav=StavHry.FAILED, chyby=[chyba])
        return Hra(slug=slug, zadani=zadani, koncept="", mapa=None, karty=[], report=report)

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
    editorial = faze4_redaktor(klient, karty, koncept, zadani, mapa)

    # simulace pro report
    _, sim_mapa = validuj_par_30_60(mapa, zadani, koncept)
    sim_reports = sim_mapa["60"] + sim_mapa["30"]

    chyby: list[str] = []
    if any(not f.verdikt for f in fit):
        chyby.append("některé karty nesedí na A5 (fit-check)")
    if any(not v.verdikt for v in editorial):
        chyby.append("redakční posudek našel nedostatky (viz editorial_report)")
    neopravitelne = sorted({e["karta"] for e in log if e.get("volby_neopravitelne")})
    if neopravitelne:
        chyby.append(f"volby na kartách {neopravitelne} neodpovídají grafu (O1, viz log)")

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
