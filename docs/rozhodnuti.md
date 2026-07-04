# Rozhodnutí (Decision Log)

> Kde zadání nebo engine mlčí, rozhodujeme **konzervativně** a rozhodnutí
> zapisujeme sem (zadání §0). Formát: datum · kontext · rozhodnutí · důvod.

---

## 2026-07-03 · Umístění repa
Nový čistý repozitář `Projects/honbicka-factory/` dle spec §2. Starší
prototyp `Projects/honbicka/` (reportlab, jiná struktura, bez testů)
ponecháván beze změny; přenášíme z něj jen engine `SKILL.md` a později
hotový skin `princezna_drak_na_louce` jako golden fixture. **Důvod:** spec
předepisuje jinou strukturu, WeasyPrint a testy — čistý build je věrnější
zadání než refaktor.

## 2026-07-03 · Autorita engine
Pořadí autority herní mechaniky: `engine/DODATKY_3.4.md` > `engine/SKILL.md`.
Engine se nikdy neobchází ani „nevylepšuje" bez pokynu v zadání (spec §0, §12).

## 2026-07-03 · Profily délky — jen 30 a 60
Factory generuje z každého principu VŽDY pár 30min (core) + 60min (master),
spec §5. Engine profil **90 min se nepoužívá**. **Důvod:** spec §5 fixuje
pár 30/60; 90min není v žádném factory požadavku ani v YAML/batch schématu.

## 2026-07-03 · Věková pásma — dvě sady, mapování
- **Factory taxonomie / YAML / složky `hotove_hry/`** (spec §7, §8):
  `04-06, 06-09, 09-12, 12-15, 16plus`.
- **Engine věkové adaptace** (SKILL.md): `4-6, 7-10, 11-14, 15-18, dospeli`.
- Zadání (`Zadani.vek`) přijímá factory pásma; `taxonomie.py` je mapuje na
  engine pásma pro architekta/vypravěče. Mapování:
  `04-06→4-6`, `06-09→7-10`, `09-12→11-14`, `12-15→15-18`, `16plus→dospeli`.
  **Důvod:** spec §7/§8 jsou pro člověka (třídění), engine pásma řídí obsah;
  potřebujeme obojí a jednoznačný převod.

## 2026-07-03 · Pásmo AHA pro archetypy bez explicitního pravidla
Dodatek 3.4-2 dává pásmo jen A1/A4/A7 (65–80 %) a A2 (68–85 %). Pro
A3/A5/A6 chybí → **default 65–80 %** (základ SKILL.md). **Důvod:**
konzervativní návrat k původní engine konstantě, dokud spec neřekne jinak.

## 2026-07-03 · M2 · Rozsah deterministických validátorů
- `topologie.py` řeší Patro 1 body 1–4 + integritu hran + garantovaný návrat
  (uzel→cíl reverzní BFS) + topologická minima proporcionálně počtu karet
  (plná od 20 karet, jinak `round(minimum × N/20)`, min 1).
- `skalovani.py` řeší počty odvoditelné z grafu (typy uzlů, komponenty, kostka
  %, práh počítadla). **Koncept-úrovňové počty** (falešné teorie, pravdivé
  stopy, konce) nejsou v grafu mapy → předávají se volitelně; naplní je **M3**
  z konceptu. Bez nich se přeskočí. **Důvod:** teorie/stopy/konce jsou
  narativní (engine FÁZE 2), architekt je do grafu nedává; nebudujeme model
  spekulativně.
- **Dokončitelnost dle archetypu (bod 6)** a **komponenty ≥2 cestami (bod 7)**
  odloženo do **M3**, kde architekt + koncept definují řešení/komponenty.
  Body 10 (slovník), 11 (bezpečnost úkolů), 13 (bypass) závisí na textu
  karet → **M4**.

## 2026-07-03 · M2 · Počítání „postav" a délkové pásmo
- „Postavy" pro §SKÁLOVÁNÍ = uzly typu POSTAVA + LECITEL; OBCHODNIK se počítá
  zvlášť (má vlastní řádek tabulky). **Důvod:** engine říká „i léčitel je
  postava", ale tabulka odlišuje obchodníka.
- Tempo simulace: venku 2,5 min/karta, uvnitř (byt/hotel) 1,75 (střed 1,5–2).
  Přijatelný medián délky: 30min → 18–48 min, 60min → 36–96 min (tolerance
  kolem nominálu; přesná délka závisí na detourech). **Důvod:** spec §6/engine
  dávají tempo, ne tvrdou hranici; pásmo drží medián u profilu bez přefitování.

## 2026-07-03 · M3 · Koncept jako samostatný výstup architekta
FÁZE 1 má dvě LLM volání architekta: (1a) `Koncept` (teorie/stopy/konce +
mechanismus řešení a rekvizita pro registr), (1b) `Mapa`. **Důvod:** spec §12
„negeneruj celou hru jedním promptem, drž úlohy malé a schematické"; koncept
navíc dodává počty, které graf mapy nenese (napojení na `skalovani`).

## 2026-07-03 · M3 · Opravná smyčka a validátor jako závislost
`faze1_architekt` má injektovatelný `validator` (default = pár 30/60 přes
`validuj_par_30_60`). Smyčka: max 4 iterace → relosování seedu (`seed+1`,
zachovává okna zákazů) → max 2×, pak FAIL. Schéma-chyba mapy (pydantic) je
běžná opravná iterace; tvrdý fail LLM (`HonbickaLLMError`) probublá nahoru
jako fail úlohy (spec §1/§4). **Důvod:** oddělení řídicí logiky od fixtur
umožňuje testovat smyčku bez GPU i bez velké 60min mapy.

## 2026-07-03 · M3 · Body 6/7 přesunuty do M4
Dokončitelnost dle archetypu (bod 6) a „komponenta dosažitelná ≥2 cestami,
gated nikdy jediná cesta" (bod 7) zůstávají odloženy do **M4**. **Důvod:**
faithful kontrola vyžaduje, aby koncept rozlišil povinné vs. návnadové
komponenty a architekt stavěl skutečné alternativní trasy; jinak by přísná
edge/uzel-disjunktní kontrola padala i na legitimních mapách s onboarding
trychtýřem. Implementuje se, až koncept ponese seznam povinných komponent.

## 2026-07-03 · M4 · Fit-check přes injektovatelný measurer
`fit_check_karty(karta, measurer=...)` měří výšku strany. **Default measurer
používá reálný WeasyPrint render** (spec §6: ne odhad znaků); když chybí GTK,
vyhodí `SazbaNedostupna` — **nikdy tiše neodhaduje** (spec §12). Testy dodají
fake measurer. **Důvod:** GTK na tomto Windows stroji chybí (WeasyPrint se
naimportuje, ale nenačte Pango/cairo); přesto musí jít logika testovat bez GPU
i bez GTK a reálný check zůstat poctivý. Rozpočet znaků (~1300–1500/strana) je
jen vodítko pro vypravěče, ne náhrada fit-checku.

## 2026-07-03 · M4 · Geometrie A5 a ořez atmosféry
Karta A5: okraje 10 mm, hlavička 12 mm, patička 8 mm → využitelná výška
170 mm, limit s rezervou 4 % = 163,2 mm; šířka obsahu 128 mm. Při přetečení:
max 3 pokusy „zkrať o N %" přes LLM, pak **deterministický ořez atmosférického
odstavce** (po 3 slovech, floor 200 znaků, končí „…") — NIKDY se neořezává
mechanika/volby. Když přetéká zadní strana (mechanika), fit-check zůstane
FAIL. **Důvod:** spec §4 FÁZE 3 + §6; číslo a typ karty řídí graf (přepisují
se z uzlu), ne LLM.

## 2026-07-04 · M5 · Imposice karet (řešení rozporu §6)
Spec §6 si protiřečí: „karta A5 na výšku 148×210" vs. „2 na A4 na výšku nad
sebou, řez vodorovně" (geometricky nemožné pro portrait). **Rozhodnutí
(potvrzeno uživatelem):** karta zůstává **portrait 148×210**, tiskne se **2
vedle sebe na A4 na šířku, svislý řez uprostřed**, duplex „otáčet po delší
straně". Přebíjí slovo „vodorovně" v §6; zachovává rozměr karty i hotový M4
fit-check. Zadní strany jsou ve STEJNÉM vodorovném pořadí (levá zůstává levá
po překlopení po delší straně) — ověřuje kalibrační arch.

## 2026-07-04 · M5 · Počet stran a validace bez GTK
Počet stran PDF = **2 (kalibrace) + 2×⌈N/2⌉** (přední+zadní arch na dvojici
karet). Validuje se **deterministicky z HTML** (počet `.arch` divů), protože
GTK zde chybí a reálný render nelze spustit; reálný render (WeasyPrint,
`full_fonts=True`) je guardovaný `SazbaNedostupna`. Pasti WeasyPrint (§6) jsou
CSS konstanty: `body margin:0`, karty `position:absolute` (ne flex/grid),
DejaVu Sans, emoji → textové symboly ▶✓✗◆.

## 2026-07-04 · M5 · Průvodce z dostupných dat
Průvodce sestavuje všechny sekce §6 (spoiler, správná odpověď, rozmístění,
checklist s doslovnými časy, brífink, EPILOG nahlas, kdy zasáhnout, QA+redakce
s citacemi, 5 feedback otázek, tisková instrukce, příloha s obsahem karet).
`brifink` a `epilog` jsou volitelné parametry; když chybí, skládají se z
konceptu. **Důvod:** bohatá epilog-próza je LLM výstup (dolaď M7/M8), ale
struktura průvodce musí být kompletní už v M5.

## 2026-07-04 · M6 · Koncept-počty jen proti 60min masteru
`validuj_par_30_60` kontroluje koncept-počty (teorie/stopy/konce) jen proti
60min grafu; pro 30min CORE se přeskočí. **Důvod:** jeden princip má jeden
`Koncept` popisující 60min master (§5: „zapisují JEDNOU"), a 30min je jeho
podmnožina — 60min chce 2 teorie, 30min 1; jedna hodnota nemůže projít oběma.
Strukturální počty (uzly) se pro 30min kontrolují dál.

## 2026-07-04 · M6 · Délka z počtu karet, ne z beeline
`zkontroluj_simulaci` ověřuje délku profilu přes `odhad_delky_min(mapa)` =
Σ tempo přes karty (2,5 min/kartu venku), NE přes nejrychlejší simulovaný
průchod. **Důvod:** 60min „master" sdílí CORE s 30min hrou, takže nejrychlejší
průchod je krátký (~22 min) — délku profilu nese počet karet a jejich průzkum
(engine: „min/kartu"). Simulační průchod slouží jen pro pozici AHA a
dosažitelnost.

## 2026-07-04 · M6 · Redaktor + měkký fail PDF
FÁZE 4 (redaktor R1–R7) je součást `vyrob_hru`. Každý verdikt se ověří
grepem citací v kartách; bez existující citace je verdikt zneplatněn
(spec §3/§12). Neúspěšné R-checky ani nesedící karty **neshazují hru** —
zapíší se do `report.chyby` (spec: „jedna vadná karta neshazuje balíček").
PDF krok bez GTK selže měkce (`report.chyby`), data hry zůstanou platná.
Plná opravná re-generace karet dle redakce je odložena do M8.

## 2026-07-04 · M7 · Téma-generátor řídí jen téma, plán řídí věk/formát
`vygeneruj_tema` dostane věk a formát z batch plánu jako TVRDÁ omezení a po
LLM výstupu je přepíše (LLM navrhuje jen tema/prostredi/obtiznost/ton).
Diverzita: kontext posledních 10 záznamů registru + max 3 vyplněné playtesty.
**Důvod:** spec §8 (plán = kombinace věk×formát×počet, bez tématu) a §3.1.

## 2026-07-04 · M7 · Dávka: FAILED nezastaví běh
`spust_davku` obaluje každou hru `try/except Exception` → FAILED se zapíše do
reportu a dávka pokračuje (spec §10). CLI `gen`/`batch` konstruují klienta přes
`_vytvor_klienta()` (testy monkeypatchnou); reálný běh vyžaduje Ollamu a pro
PDF/fit-check GTK. Knihovní funkce (`spust_davku`, `vygeneruj_tema`, YAML)
jsou testované s mockem a fake measurerem.

## 2026-07-04 · M8 · Golden game bez LLM + živý E2E jako smoke
- **Golden game** (`test_golden.py`): pevná 60-uzlová mapa + deterministické
  karty projdou validací a sazbou bez LLM → stabilní počet stran (60→22,
  30→14), fit-check zelený, zadní strany neprohozené, kalibrační arch.
- **Živý E2E** (`test_e2e_live.py`, `@slow`): ověřuje LLM vrstvu proti reálnému
  `qwen3.6:27b` (téma-generátor → Zadani, architekt → Koncept se parsují).
  **Neověřuje** plně validní živě vygenerovanou hru — architekt 27B nemusí
  vyrobit validní 20-uzlový graf za pár iterací; to je vlastnost modelu, ne
  pipeline, a ověřuje se ručně. **Důvod:** live test má být deterministicky
  přeskočitelný (bez Ollamy) a ne-flaky; kontrakt klienta/schémat byl ověřen
  reálným voláním (téma-generátor vrátil validní JSON za ~29 s).

## 2026-07-04 · M8 · Robustnost vůči nedokonalému výstupu modelu
Živý E2E odhalil, že `qwen3.6:27b` i se structured outputem vrací hodnoty
mimo enum ('lehká' místo 'lehka') a občas vynechá pole. `vygeneruj_tema`
proto vkládá plán-autoritativní pole (věk/formát) PŘED validací a normalizuje
diakritiku enumu obtížnosti. **Důvod:** structured output garantuje tvar JSON,
ne přesné hodnoty enumů/požadovaných polí; místa, kde plán/graf zná správnou
hodnotu, ji mají doplnit před `model_validate`. Regrese pokryta unit testem
(`test_vygeneruj_tema_robustni_vuci_nedokonalemu_modelu`).

## 2026-07-04 · M8 · Živý shakedown architekta → posílení promptu
Diagnostika `_zavolej_architekta` proti reálnému `qwen3.6:27b` (téma „cesta
kapky vody", seed 42, 21 uzlů) odhalila, že vágní prompt vedl k mapě bez hran
(96 chyb: vše osiřelé/softlock). Postupné posílení `_prompt_architekt`:
1. explicitní struktura hran (`hrany:[{cil:N}]`) + příklad uzlu → **96→9 chyb**
   (všechny uzly dostaly hrany);
2. gated/strez/slepé mají vstupní hrany + CORE musí samo splnit 30min počty
   → zmizely chyby souvislosti i CORE škálování;
3. klíčová svědectví jen 2–3 na povinné ose + CORE ≥2 rozcestí/≥1 smyčka
   (dominátorové umístění, zbývající třída chyb).
**Zjištění (operační):** architekt (thinking ON, 21-uzlový graf) trvá
~380–450 s / volání; koncept ~165 s. FÁZE 1 s opravnou smyčkou tak může trvat
desítky minut — akceptovatelné pro noční dávku, ne pro interaktivní běh.
Reziduální chyby prvního pokusu jsou přesně ty, které opravná smyčka dostává
jako cílené diagnostiky, takže konvergence je reálná (na rozdíl od původního
stavu). **Plná konvergence živého běhu ověřena empiricky na trajektorii chyb,
ne kompletním during-noc během** (GPU čas).

## 2026-07-04 · M8 · Opravná re-generace karet dle redakce — odloženo
Plná zpětná smyčka FÁZE 4→3 (redaktor označí karty → vypravěč přepíše) není
implementována; neúspěšné R-checky se zapisují do `report.chyby` a hru
neshazují (spec: „jedna vadná karta neshazuje balíček"). **Důvod:** vyžaduje
mapování citací na konkrétní karty a cílený re-prompt; hodnota vs. riziko
nízká pro první verzi, kontrakt (ověření citací) je hotový. Kandidát na
budoucí iteraci.

## 2026-07-03 · LLM klient — mockovatelnost
`llm.py` volá Ollama přes HTTP (`/api/chat`, `format` = JSON schema). Klient
je plně injektovatelný/mockovatelný, aby testy (mimo `@slow`) nikdy
nepotřebovaly GPU ani běžící Ollamu. **Důvod:** spec §10 vyžaduje golden/e2e
testy bez živého modelu; jediná síťová závislost za běhu je localhost Ollama
(spec §12).
