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

## 2026-07-04 · M8 · Plný živý FÁZE 1 loop → NEKONVERGUJE (klíčové zjištění)
Plný živý běh opravné smyčky (12 iterací, 93 min, seed 42) proti
`qwen3.6:27b` **nedokonvergoval** na validní mapu. Chybovost osciluje kolem
~2 (nejlepší pokus: 2 chyby), ale model nikdy netrefí 0. Inkrementální oprava
(přiložení předchozí mapy + „oprav jen tohle") oscilaci zmírnila, ale model
i tak rozbíjí dříve správné části.
**Nejtěžší třída chyb = grafové dominátory:** „klíčové svědectví/AHA uzel není
na povinné trase", „pozice AHA 92 %", opakovaně osiřelé uzly. Vyžadují úvahu,
kterými uzly projde KAŽDÁ cesta — a musí platit současně pro plný graf i CORE
podgraf. To je pro 27B model generující JSON nespolehlivé.
**Diagnóza:** pipeline i validátory jsou správné a přísné; problém je, že LLM
má splnit tvrdé topologické invarianty, které mají dle spec §3 („LLM tvoří,
Python rozhoduje") patřit deterministickému kódu.
**Doporučený fix (nový pracovní balík, nad rámec M1–M8):** deterministický
**graf-scaffolder / auto-repair** — LLM dodá kreativní obsah (regiony, témata
uzlů, kdo nese stopu, beaty archetypu), Python zaručí souvislost, dominátory
klíčových svědectví a AHA uzlu, a validitu CORE podgrafu (dopojí osiřelé,
přesune/omezí klicove_svedectvi na spočtený trunk, ořízne komponenty na 2,
dorovná CORE flagy). Tím se konvergence stane deterministickou.
Levnější experiment: zkusit `qwen3-coder:30b` (lokálně dostupný) — coder model
může být lepší v produkci strukturovaných grafů.
**Sonda coder modelem (2026-07-04): ZAMÍTNUTO.** `qwen3-coder:30b` (thinking
off — Ollama vrací 400 na think:true u ne-thinking modelu) dal na první pokus
**54 chyb** (vs qwen3.6 = 9), navíc ignoroval CORE/SIDE (vše CORE) a graf byl
rozpojený. Rychlejší (47 s), ale výrazně horší. Závěr: thinking režim qwen3.6
je pro strukturální úvahu klíčový; přepnutí modelu problém neřeší →
**deterministický scaffolder (výše) je jediná robustní cesta.**

## 2026-07-04 · M8 · ŘEŠENÍ: deterministický scaffolder (FÁZE 1 bez LLM)
Na základě zjištění o nekonvergenci a zamítnuté coder-sondy postaven
`honbicka/scaffold.py`: `postav_skeleton` deterministicky staví graf, který
projde `validuj_par_30_60` **z konstrukce** (ověřeno **3600/3600** kombinací
věk × obtížnost × formát × prostředí × seed). Struktura: pevných 21 uzlů
(12 CORE trunk = validní 30min hra + 9 SIDE, které se sbíhají do trunku před
AHA). **AHA uzel se volí adaptivně** — simuluje se pozice AHA (v čase) pro
každý dominátor trunku a vybere se ten nejblíž STŘEDU pásma pro 30min i 60min
zároveň. Klíčová rozhodnutí při ladění:
- AHA uzel = ten centrovaný (ne první „v pásmu" na kraji — kraj + variabilita
  simulace = občasný fail);
- scaffolder i finální validace musí použít **stejný počet průchodů** (15 —
  spec „≥5"; 5 je pro výběr uzlu příliš šumivé);
- pevných 21 uzlů (žádný proměnný SIDE filler, který rozkolísal 60min AHA);
- koncept-počty (teorie/stopy/konce) přepisuje Python z `pocty_cile`
  (LLM je občas netrefí i se structured outputem).
`vyrob_hru(pouzij_scaffolder=True)` je **default**; LLM architekt zůstává jako
legacy cesta (`False`). FÁZE 1 je tím **okamžitá, deterministická, bez rizika
konvergence** — přesně dle spec §3 „LLM tvoří (koncept, texty), Python rozhoduje
(struktura)". LLM tak dělá jen to, co umí spolehlivě.
> **Kompromis:** karetní topologie je zatím jeden pevný vzor (variabilita jde
> z archetypu, pozice AHA, prahu a témat/textů LLM). Více topologických vzorů
> je kandidát na budoucí iteraci.

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

## 2026-07-04 · VYŘEŠENO: GTK/WeasyPrint na Windows (dřívější omezení odpadá)
Dřívější omezení „GTK chybí → PDF se nevyrenderuje" bylo způsobeno **jinou
příčinou, než se předpokládalo**. Uživatel nainstaloval GTK4 a WeasyPrint
přesto hlásil `cannot load library 'libgobject-2.0-0'`. Root cause: **Python
3.8+ na Windows ignoruje proměnnou `PATH` při hledání závislostí DLL**
(bezpečnostní změna „safe DLL search mode") — knihovny GTK/Pango/cairo
existovaly (nalezeny v `C:\msys64\ucrt64\bin`), ale `ctypes`/cffi je nenašly,
dokud nebyl adresář připojen přes `os.add_dll_directory()`.

**Řešení:** `honbicka/sazba/render.py::_zajisti_gtk_dll_cestu()` — hledá GTK
knihovny (marker `libgobject-2.0-0.dll`) v seznamu známých umístění (MSYS2
`ucrt64`/`mingw64`, GTK3-Runtime, gvsbuild), nebo v `HONBICKA_GTK_DIR`
(env var), a připojí nalezený adresář přes `os.add_dll_directory()`. Voláno
idempotentně před každým importem `weasyprint` (`je_dostupne()`, `zapis_pdf()`,
`validatory/sazba.py::_weasy_measurer()`). **Ověřeno end-to-end:** reálný A5
fit-check i reálné PDF (karty 60/30min, herní list, průvodce) vyrenderovány
z dat živě vygenerované hry „čtyři světla"; počet stran v PDF (24/14/2/9)
přesně odpovídá `pocet_stran()`. **Důvod:** centralizace v jednom místě
(`render.py`) místo opakování detekce na obou importních místech; env var
je únikový poklop pro netypická umístění GTK. Testováno v `tests/
test_render_gtk.py` s injektovaným seznamem kandidátů (deterministické,
nezávislé na tom, jestli testovací stroj GTK skutečně má).

## 2026-07-04 · OPRAVENO: `importlib.reload()` v testu trvale poškozoval GTK detekci
Při práci na Vlně 2 auditu se plná testovací sada náhodně rozpadla na
`SazbaNedostupna` v testech, které dřív spolehlivě renderovaly reálné PDF.
Příčina: `tests/test_render_gtk.py::test_env_var_je_prvni_kandidat` testoval
prioritu `HONBICKA_GTK_DIR` přes `importlib.reload(honbicka.sazba.render)`.
`importlib.reload()` ale NEVYTVOŘÍ nový modul — přepíše jména VE STEJNÉM
namespace dictu, který sdílejí i funkce importované jinam přes `from render
import X` (jejich `__globals__` ukazuje na TENTÝŽ dict). Reload proto
znovu-vyhodnotil `_GTK_KANDIDATI_WIN = [os.environ.get(...), ...]` — a
protože se to stalo v okamžiku, kdy testovací fixtura dočasně nastavovala
`HONBICKA_GTK_DIR` na dočasný (mizející) adresář, tahle FALEŠNÁ cesta se
natrvalo zapekla do modulové konstanty pro **zbytek celého test procesu** —
`monkeypatch` to nemohlo vrátit zpět, protože reload není monkeypatch.
Následné testy pak nacházely jen tento neplatný adresář a nikdy se
nedostaly k reálné MSYS2 cestě → `SazbaNedostupna`.

**Oprava:** `_GTK_KANDIDATI_WIN` (modulová konstanta zamrzlá při importu)
nahrazena funkcí `_gtk_kandidati()`, která `HONBICKA_GTK_DIR` čte ČERSTVĚ
při každém volání `_zajisti_gtk_dll_cestu()`. Test env-var priority teď jen
`monkeypatch.setenv(...)` + přímé volání — žádný `importlib.reload()`
nikde v testech. **Poučení:** `importlib.reload()` v testu je nebezpečný,
pokud modul má funkce importované jinam přes `from X import Y` — sdílejí
`__globals__`, takže reload ovlivní i STARÉ reference v jiných modulech,
a mutace (na rozdíl od `monkeypatch`) se sama nevrátí. Řešení „čti stav za
běhu, ne jednou při importu" je obecně bezpečnější pattern pro cokoliv,
co testy potřebují měnit.

---

## 2026-07-05 — L1: `generuj_model` zapojen jen do `vygeneruj_tema`

Úkol L1 žádal sjednocené `generuj_model(role, prompt, Model) -> Model` v
`honbicka/llm.py`, které v JEDNÉ retry smyčce řeší `json.loads` +
`Model.model_validate` + opravný prompt s pydantic chybami (dřív každé
volající místo řešilo pydantic validaci jinak: architekt error-tuple,
vypravěč vlastní retry, koncept/téma tvrdě padaly).

**Rozhodnutí: `generuj_model` se NEzapojuje do `faze1a_koncept`,
`_zavolej_architekta` ani `napis_kartu`.** Jejich retry smyčky nesou
sémantiku specifickou pro danou roli, kterou generická JSON+pydantic
smyčka nepokryje beze ztráty:
- architekt: retry řeší i game-validity feedback (topologie/škálování),
  ne jen tvar JSONu — a při vyčerpání iterací jde o RELOSOVÁNÍ seedu, ne
  jen o chybovou hlášku;
- vypravěč: retry řeší O1 fit-check (rozpočet znaků) a platnost čísel
  voleb vůči grafu — obojí vyžaduje `mapa`/`uzel` v kontextu, který
  `generuj_model` nezná;
- koncept: má vlastní mechanickou poslední záchranu
  (`_normalizuj_koncept_data`) PŘED tvrdým selháním — jiný tvar smyčky
  než „oprav prompt a zkus znovu".

**`vygeneruj_tema` — druhá překážka, ne jen jednodušší call site.**
Očekávalo se, že jde o „ten jeden čistý call site", ale narazilo se na
past: `Zadani.vek` je POVINNÉ pole, které model nespolehlivě vrací (viz
`test_vygeneruj_tema_robustni_vuci_nedokonalemu_modelu` — živý model
`vek` občas vůbec nevrátí). Plán (`vek`, `format_hracu`) je autoritativní
a musí se do dat propsat PŘED validací — `generuj_model` ale validuje
HNED, takže chybějící `vek` by u živého modelu zbytečně vyčerpal retries
a nakonec spadl, přestože oprava je triviální (přepsat, ne dohledávat).
Proto `vygeneruj_tema` zůstává na `generuj_json` + ruční patch dictu →
`Zadani.model_validate`. Normalizace diakritiky u `obtiznost`
(`'lehká'` → `'lehka'`) se ale přesunula z volající funkce do
`field_validator(mode="before")` přímo na `Zadani` — nezávislé vylepšení,
funguje bez ohledu na to, kudy se model validuje.

**Závěr:** `generuj_model` existuje jako hotová, otestovaná primitiva
(`tests/test_llm.py`) pro budoucí call sites, kde požadavek „over přes
LLM → pydantic model" sedí 1:1 bez business-logiky mezi tím. Žádné
současné volající místo v `orchestrator.py` ten tvar splňuje kromě
(s výhradou výše) téma-generátoru — a ani ten napřímo, proto zůstal na
staré cestě.

## 2026-07-05 — L2/L3: fallback bez thinking + retry na přechodnou chybu

`_http_transport` teď rozlišuje tři případy HTTP/transportní chyby:
- HTTP 400 **s `think:true`** v payloadu → `_ThinkingNotSupported` (model
  neumí thinking — živě ověřeno sondou `qwen3-coder:30b`, vrací 400 na
  `think`, funguje bez něj).
- HTTP 5xx nebo `Timeout`/`ConnectionError` → `_PrechodnaChyba` (dočasná,
  1 opakování má smysl).
- cokoliv jiného (jiné 4xx, DNS, …) → normální `HonbickaLLMError` beze
  změny chování.

`OllamaKlient._volej` na `_ThinkingNotSupported` reaguje JEDNÍM pokusem
bez thinking; pokud role už `thinking=False` měla, nebo selže i podruhé,
je to tvrdý fail (max 2 HTTP pokusy, žádná nekonečná smyčka). `_volej_pokus`
na `_PrechodnaChyba` zkusí 1× zopakovat, pak tvrdý fail — bez logování
(vědomě odloženo, drobný dluh pro pozorovatelnost, viz `docs/navrhy_vylepseni.md`
L3).

Nebyla implementována detekce schopností modelu předem přes `/api/show` —
jednodušší a méně křehké je reagovat až na skutečné HTTP 400, ne
modelovat/cachovat schopnosti modelu dopředu (a riskovat, že cache
zestárne, když se model v Ollamě přehraje).

---

## 2026-07-05 — MD2: pravdivost stop implementována jen částečně

`Uzel.pravdivost: Pravdivost | None` (pravda/zavadejici/lez) přidán do modelu
a scaffolder ho teď reálně přiřazuje INFORMACE uzlům dle `koncept.pravdive_stopy`
(první N uzlů dle čísla → PRAVDA, zbytek střídavě LEZ/ZAVADEJICI). Audit MD2
navrhoval jít o krok dál: nechat `skalovani.zkontroluj_skalovani` počítat
SKUTEČNÝ počet pravdivých stop z mapy a nahradit jím (nebo zkřížit s) číslo
`koncept.pravdive_stopy`.

**To se záměrně NEudělalo.** Pevná scaffolder kostra má jen 2 INFORMACE uzly
v CORE (30min) a 3 celkem (60min) — a `pravdive_stopy_min` je přesně 2/3.
Na hranici (typický/minimální případ) tak vyjdou VŠECHNY INFORMACE uzly jako
PRAVDA a nezbyde žádný pro LEZ/ZAVADEJICI. Striktní kontrola
`count(uzel.pravdivost==PRAVDA) == koncept.pravdive_stopy` by proto scaffolder-
mapy protrhla přesně v běžném, ne okrajovém případě — false positive na
každé hře na spodní hranici škálování.

Skutečná oprava vyžaduje jedno z:
1. Rozšířit pevnou kostru o další INFORMACE uzly (topologická změna — riziko
   pro už vyladěné AHA-timing/topologická minima, viz SC1/V1/AHA sekce výše).
2. Rozšířit `pravdivost` i na svědectví z POSTAVA/LECITEL uzlů
   (`klicove_svedectvi=True`) — SKILL.md §INFORMACE JSOU ODMĚNA mluví
   primárně o uzlu `informace`, ale zmiňuje i vazbu na motivace postav (P8),
   takže rozšíření by nebylo mimo ducha spec, jen vyžaduje další modelovací
   rozhodnutí (kde přesně na POSTAVA/LECITEL kartě se pravdivost projeví).

Obojí je větší zásah než jedna 🟡 položka auditu unese bez živého ověření.
Rozhodnutí: nechat `pravdivost` jako METADATA na INFORMACE uzlech (R1/R2 teď
mají aspoň částečnou datovou oporu — hodnota reálně existuje a je
deterministicky odvozená), ale NEpřidávat tvrdou skalovani kontrolu nad
touto hodnotou, dokud topologie nemá prostor ji bezpečně unést. Kandidát na
Vlnu 4/budoucí session — spolu se SC2 (topologická variabilita), protože obě
řeší stejný kořen: pevná 21-uzlová kostra je jeden strukturální kompromis a
další zpřesnění nad ní (víc INFORMACE uzlů, víc vzorů trunku) patří dohromady.

---

## 2026-07-05 — SC2: topologická variabilita analyzována, implementace odložena

Audit SC2 žádá strukturální variabilitu scaffolderu (dnes jeden pevný
21-uzlový vzor pro každou hru) — jinak si opakovaní hráči vzor zapamatují.
Navržené cesty: (a) prohodit pořadí hran u forků, (b) posunout GATED/STREZ
pozice, (c) střídat 2–3 předpřipravené vzory trunku.

**Rozhodnutí: neimplementovat v této dávce.** Důvody:

1. **(a) je kosmetické nanic.** Uzly 3 a 4 (fork z uzlu 2) jsou už teď
   strukturálně identické (stejný typ INFORMACE, stejný fork/rejoin bod) —
   prohození jejich pořadí v `hrany` listu nic nezmění, protože jsou
   vzájemně zaměnitelné. Skutečnou „jinou strukturu" by hráč nepoznal.

2. **(b)/(c) jsou rizikové.** `_vyber_aha_uzel` (honbicka/scaffold.py) hledá
   kandidáty na AHA uzel VÝHRADNĚ v CORE podgrafu (`core_cisla` filtr) a
   vybírá ten, jehož mediánová simulovaná pozice AHA (napříč 30min i 60min
   profilem) je nejblíž středu pásma archetypu. Tahle volba byla ověřena
   simulací přes celou seed×věk×obtížnost×formát mřížku (3600 kombinací,
   viz M8 zjištění a dřívější záznamy v tomto souboru) — jakákoli změna CORE
   topologie (jiné větvení, jiné pozice STREZ/GATED) by tohle ověření musela
   zopakovat celé, jinak riskuje TICHÉ porušení AHA-banding u okrajových
   archetypů/seedů (chyba, kterou `test_skeleton_projde_validaci` — pokrývá
   jen `range(14)` seedů — nemusí odhalit).

3. **Nalezena bezpečnější podmnožina, ale i ta vyžaduje novou práci.** SIDE
   region (uzly 13–21, jen 60min) NENÍ součástí AHA-kandidátního hledání
   (to je čistě `core_cisla`), takže alternativní SIDE topologie (zachovávající
   stejný multiset typů kvůli `skalovani`, jiné pořadí fork/rejoin uvnitř)
   by nesla podstatně nižší riziko. Pořád by ale vyžadovala ručně navrženou
   DRUHOU kostru a její ověření přes existující topologické/škálovací/
   simulační kontroly — ne jen náhodné zamíchání parametru `rng` (ten dnes
   zůstává nevyužitý, jak audit správně poznamenává).

**Pro budoucí session:** začít u SIDE regionu (nižší riziko), NE u CORE
trunku. Návrh postupu: (1) navrhnout druhou SIDE topologii se stejným
type-multisetem (1× LECITEL, 2× POSTAVA-ish, 1× SLEPA, 1× STREZ, 1×
INFORMACE, 1× GATED, 1× OBCHODNIK, 1× SMYCKA, 1× JEDNOSMER — dnešní
rozložení uzlů 13–21), (2) `postav_skeleton` losuje mezi oběma přes `rng`
(default `random.Random(params.seed)` pro reprodukovatelnost), (3) ověřit
oba vzory přes STEJNOU parametrizovanou sadu seedů/věků/obtížností/formátů
jako `test_skeleton_projde_validaci`, včetně nového vzoru v maticích.
Viz také zápis „MD2: pravdivost stop" výše — obě položky sdílí kořen (pevná
kostra jako záměrný kompromis) a patří spolu do stejné budoucí revize topologie.
