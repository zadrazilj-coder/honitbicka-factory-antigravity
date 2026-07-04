# HONBIČKA FACTORY

[![CI](https://github.com/zadrazilj-coder/honbicka-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/zadrazilj-coder/honbicka-factory/actions/workflows/ci.yml)

Autonomní agentní systém pro sériové generování venkovních karetních her
(engine **Honbička 3.3/3.4**) na lokálním hardwaru. Z jednořádkového zadání —
nebo zcela automaticky v dávce — vyrobí kompletní tisknutelnou hru a zvládne
jich vyrobit desítky, roztříděné podle věku a počtu účastníků, bez lidského
zásahu (iteruje, dokud validace neprojde).

> **Engine = jediný zdroj pravdy.** Herní mechanika je v `engine/SKILL.md`
> (Honbička 3.3) + `engine/DODATKY_3.4.md` (přebíjí SKILL.md). Nikdy se
> neobchází ani „nevylepšuje". Rozhodnutí tam, kde spec mlčí, jsou v
> `docs/rozhodnuti.md`.

## Stav (milníky)

- [x] **M1** — skeleton + Ollama klient + schémata + testy
- [x] **M2** — validátory (topologie, škálování) + simulace (BFS agent)
- [x] **M3** — FÁZE 0 losování + architekt s opravnou smyčkou
- [x] **M4** — vypravěč (karta po kartě) + A5 fit-check (reálný render)
- [x] **M5** — sazba PDF (karty 30/60, list, průvodce, kalibrační arch)
- [x] **M6** — registr + taxonomie + report + stavový stroj `vyrob_hru`
- [x] **M7** — téma-generátor + batch + feedback smyčka
- [x] **M8** — E2E (golden + `@slow` živý model) + dokumentace

## Jak to funguje (zásada)

**LLM tvoří, Python rozhoduje.** Jeden model (`qwen3.6:27b`), čtyři role
(téma-generátor, architekt, vypravěč, redaktor) se liší jen system promptem,
teplotou a thinking režimem. Veškerá herní validace (topologie, škálování,
délka, pozice AHA, A5 fit-check) je **deterministický Python** — žádný LLM.

Pipeline jedné hry (FÁZE 0–5, `honbicka/orchestrator.py`):

```
FÁZE 0  registr → okna zákazů → losování (archetyp, práh, pozice AHA)
FÁZE 1  koncept (LLM) + mapa: deterministický scaffolder staví validní graf
        (Python vlastní strukturu; LLM architekt je legacy fallback)
FÁZE 2  simulace (BFS agent) → délka + pozice AHA v čase
FÁZE 3  vypravěč karta po kartě → A5 fit-check každé karty ihned
FÁZE 4  redaktor R1–R7 s ověřenými citacemi (grep v kartách)
FÁZE 5  sazba PDF (30/60), herní list, průvodce, kalibrační arch;
        registr; taxonomie; report.json
```

Z jednoho principu vzniká **vždy pár 30min (core) + 60min (master)** — 60min
mapa má uzly značené CORE/SIDE, CORE podgraf je plnohodnotná 30min hra.

## Hardware a model

- GPU: AMD RX 7900 XTX (24 GB, ROCm). Pokud Ollama nevidí GPU:
  `HSA_OVERRIDE_GFX_VERSION=11.0.0` (gfx1100). Bez GPU běží degradovaně na CPU
  (jen pomaleji).
- Inference: **Ollama**, model `qwen3.6:27b` (~17 GB). `num_ctx`: 16384
  vypravěč, 32768 architekt/redaktor. Jediná síťová závislost za běhu je
  localhost Ollama.

## Instalace

```bash
# 1) Python balíček
python -m pip install -e ".[dev]"

# 2) Ollama + model
#    Nainstaluj Ollamu (https://ollama.com), pak:
ollama pull qwen3.6:27b
#    ROCm: pokud Ollama nevidí GPU, spusť server s:
#    HSA_OVERRIDE_GFX_VERSION=11.0.0 ollama serve

# 3) GTK runtime pro WeasyPrint (nutné pro generování PDF)
#    Windows: nainstaluj GTK3 runtime
#      (https://github.com/tschoonj/GTK-for-Windows-Runtime-Installer)
#    Linux: apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0
#    macOS: brew install pango gdk-pixbuf libffi
```

> **Bez GTK** se hra vygeneruje a zvaliduje (koncept, mapa, karty, fit-check),
> ale PDF se nevyrenderuje — `report.chyby` to zaznamená a hra zůstane datově
> platná. A5 fit-check vyžaduje reálný render, takže bez GTK nelze potvrdit
> vejití karet na stránku (nikdy netiskneme „naslepo" — spec §12).

## Použití

```bash
honbicka gen zadani/hra.yaml       # jedna hra → vyrobí 30min i 60min verzi
honbicka batch zadani/plan.yaml    # dávka přes noc (témata z téma-generátoru)
honbicka new                       # interaktivní pomocník → YAML do zadani/
honbicka feedback <slug>           # šablona playtestu → skiny/<slug>/
honbicka status                    # přehled běhů a registru
```

Zadání jedné hry (`zadani/hra.yaml`) i dávkový plán (`zadani/plan.yaml`) jsou
přiloženy jako příklady.

## Kde jsou výstupy

- `skiny/<slug>/` — pracovní balíček: `koncept.md`, `mapa.json`, `karty.json`,
  PDF (karty 30/60, herní listy, průvodci), `report.json`, `log.jsonl`,
  `playtest_vysledky.md`.
- `skiny/registr.md` — append-only registr her (okna zákazů proti opakování).
- `hotove_hry/vek_<pásmo>/<formát>/<slug>_<30|60>min/` — finální roztříděné
  kopie pro lidi + `INDEX.md` (anotace bez spoilerů + co vytisknout).

## Tisk karet

Karty A5 na výšku (148×210), **2 vedle sebe na A4 na šířku, svislý řez
uprostřed**, duplex „otáčet po delší straně". Každé PDF karet začíná
**kalibračním archem** (strana 1–2) — vytiskni ho první a ověř zákryt proti
světlu, než tiskneš celou sadu.

## Testy

```bash
python -m pytest                 # rychlé testy (bez GPU/GTK) — mockovaný LLM
python -m pytest -m slow         # E2E s živým modelem (vyžaduje Ollamu)
python -m ruff check honbicka tests
```

Rychlé testy nikdy nepotřebují GPU, GTK ani běžící Ollamu (LLM klient i A5
measurer jsou plně mockovatelné). `@slow` testy ověřují LLM vrstvu proti
reálnému `qwen3.6:27b` a přeskočí se, když Ollama neběží.

## Ladění

- **Co se dělo v běhu:** `skiny/<slug>/log.jsonl` — každá iterace (fáze,
  seed, chyby). `report.json` — validace, redakční verdikty, fit-check tabulka.
- **Hra selhala (FAILED):** FÁZE 1 nenašla validní mapu za 4 iterace × 3
  seedy. `report.chyby` a `log.jsonl` obsahují diagnostiky (např. „AHA v 91 %,
  přesuň klíčové svědectví…").
- **Reprodukce:** seed je v reportu i registru; `vyrob_hru(..., seed=<N>)`
  zopakuje běh.
- **PDF chybí:** chybí GTK runtime (viz Instalace).

## Struktura

Viz zadání §2. Klíčové: `honbicka/` (balíček), `honbicka/validatory/`
(DETERMINISTICKÉ kontroly — žádný LLM), `honbicka/sazba/` (WeasyPrint),
`engine/` (SKILL.md + dodatky), `skiny/` (pracovní běhy), `hotove_hry/`
(finální roztříděné výstupy), `docs/rozhodnuti.md` (konzervativní rozhodnutí).
