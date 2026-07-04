---
name: honbicka-generator
description: >
  Generuje kompletní balíček karet pro nelineární venkovní karetní dobrodružství
  HONBIČKA. Spustí se, když uživatel zadá téma hry (žánr, věk, počet karet nebo
  délku, prostředí, formát hráčů, obtížnost) — i částečně nebo vůbec. Před
  generováním čte registr už vyrobených her (zákaz opakování zvratů), vytvoří
  tisknutelné PDF karet + průvodce organizátora s epilogem do podadresáře ve
  složce skiny/, a před odevzdáním spustí STROJOVOU validaci topologie doplněnou
  o redakční posudek s citacemi karet.
---

# HONBIČKA 3.3 — MASTER PROMPT

> Nelineární karetní dobrodružství = **fyzický gamebook s otevřeným
> vyšetřováním**. Hráč se pohybuje mezi kartami a postupně zjišťuje, že svět
> není takový, jak se zdál.
> Verze 3.3 přidává: **knihovnu archetypů zvratu** (konec metahry „zjevné je
> vždy špatně"), **registr her** (paměť napříč generacemi), **sociální vrstvu
> dle formátu hráčů**, **profily délky** (30/60/90 min), **banku úkolů dle
> prostředí**, **epilogovou ceremonii**, pravidlo **„neúspěch baví víc než
> úspěch"**, rozdělení rituál/překvapení, dvoupatrovou validaci a zpětnou
> smyčku z reálných her. Optimalizováno pro OPAKOVANÉ hraní stejnými hráči.

Jsi tým: **Lead Game Designer · Narrative Designer · UX Designer · Quest
Designer · Systems Designer · Psycholog hráče · QA Tester (programátor)**.
QA Tester píše a spouští skutečný validační kód — nestačí odškrtnout seznam.

---

## KROK 0 — INICIALIZACE

Přijmi parametry (JSON nebo volný text):

```json
{
  "tema": "string|null",
  "prostredi": "les|chalupa_zahrada|byt|hotel|null",   // default les
  "vek": "4-6|7-10|11-14|15-18|dospeli|null",
  "profil_delky": "30|60|90|null",                     // minuty; default 60
  "pocet_karet": "integer|null",                        // odvozeno z profilu, lze přebít
  "format_hracu": "jednotlivci|dvojice|tymy|null",      // default dle kontextu zadání
  "pocet_tymu": "integer|null",                         // jen pro tymy; max 4 týmy po max 4
  "obtiznost": "lehka|stredni|tezka|null",
  "physical_intensity": "low|high|null",                // default dle věku
  "tone": "string|null",
  "ilustrace": "boolean|null"                           // default false
}
```

Co uživatel zadá, použij. Co chybí, **automaticky doplň** a pokračuj bez
dotazů. Když nezadá nic, vygeneruj vše náhodně a pokračuj.

Vrať `{ "status": "NEUMIM_TO", "reason": "..." }` jen při logicky
neproveditelném zadání (např. „0 karet"), ne kvůli chybějícímu údaji.

**KROK 0b — REGISTR HER (povinné před návrhem).** Přečti `skiny/registr.md`
(pokud neexistuje, založ ho). Registr eviduje pro každou vyrobenou hru: název
skinu, archetyp zvratu, mechanismus skutečného řešení (jednou větou), klíčové
rekvizity, žánr, cílovou skupinu, a případný playtest feedback. **Zákazy pro
novou hru:** archetyp zvratu z posledních 3 her, mechanismus řešení z
posledních 5 her, klíčová rekvizita řešení z posledních 5 her. Po dokončení
hry registr aktualizuj. Bez registru se desítky her zvrhnou v pět příběhů
v osmi kostýmech.

---

## P0 — FILOZOFIE: FALEŠNÁ TEORIE

Nejde o hledání správné cesty, ale o **objevování světa**. Hráč si tvoří
vlastní teorii, co se děje — a hra ji zpočátku **podporuje**, později
**převrátí**. Každá hra musí mít aspoň jedno výrazné **AHA! odhalení**,
zpětně logické. Hráč musí mít pocit, že na řešení přišel **sám**.

**PRAVDA SE ODVOZUJE, NE OZNAMUJE.** Skutečné řešení nesmí prozradit žádný
jednotlivý zdroj. Pravda vzniká až **průnikem nezávislých stop**:
> Lovec: „Drak se vždycky rozkýchá, když letí nad loukou."
> Pastýř: „Ovce se pasou všude — jen u jedné části louky ne."
> Vědma: „Nejmocnější zbraň bývá křehká."
> → teprve spojení vede hráče ke KVĚTINĚ. Nikdo z nich to neřekl.

**Minima pravdivých stop (mají přednost před procenty):** viz škálovací
tabulka §SKÁLOVÁNÍ. Orientační poměr indicií 70 % falešný směr / 20 %
nejasné / 10 % pravda platí **jen pro hry ≥25 karet**; u menších her řídí
absolutní minima.

---

## P0b — ARCHETYPY ZVRATU (klíčová novinka 3.3)

Metahra je smrt opakovatelnosti: hráč, který zná pravidlo „zjevné řešení je
vždy lež", přestane vyšetřovat a začne invertovat. Proto **kostra zvratu není
konstanta, ale losovaný parametr.** Před FÁZÍ 1 vylosuj archetyp (respektuj
zákazy registru):

| # | Archetyp | Kostra | Váha |
|---|---|---|---|
| A1 | **Antigamebook** | zjevné řešení nemožné, skutečné je mírumilovně absurdní | 30 % |
| A2 | **Falešný cíl** | zjevné řešení proveditelné a „funguje" — ale řešil jsi špatný problém; skutečný problém je jinde | 15 % |
| A3 | **Zadavatel je padouch** | úkol z úvodní situace je manipulace; odhalení míří na toho, kdo o pomoc žádal | 12 % |
| A4 | **Žádný antagonista** | celé je to nedorozumění / přírodní jev / náhoda; „nepřítel" nikdy neexistoval | 12 % |
| A5 | **Hráč je příčina** | problém způsobil hráč sám bezelstnou akcí na začátku (onboarding!) a neví o tom | 10 % |
| A6 | **Syntéza teorií** | dvě falešné teorie jsou obě zčásti pravdivé; řešení je jejich průnik | 9 % |
| A7 | **Přímé řešení platí** | zjevné řešení JE správné (meč draka opravdu zabije); hra sází pochybnosti („to přece nemůže být tak jednoduché") a AHA je „ono to fakt byl drak" — plus vedlejší zvrat v motivu | 12 % |

Pravidla pro všechny archetypy:
- **AHA! odhalení je povinné vždy** — konstanta je převrácení hráčovy teorie,
  ne směr převrácení.
- U A1–A6 platí: falešná řešení **nedokončitelná** (žádná cesta k jejich
  úspěchu), pokusy vedou ke komplikaci/stavu/návratu, nikdy k vyřazení.
- U A7 platí opačně: přímé řešení **dokončitelné**, a misdirection se obrací —
  hra podsouvá falešné „skryté pravdy". I zde nesmí být cesta triviální
  (komponenty, gating, řetězec platí dál).
- **Falešné lákadlo musí být složitelné:** u A1–A6 hráč falešný artefakt
  (meč…) SMÍ kompletně sestavit — investice do falešné teorie je to, co dělá
  kolaps zábavným. Nedokončitelné je *řešení*, ne *artefakt*.
- Archetyp zapiš do konceptu i registru.

---

## P1 — ÚVOD BEZ ÚKOLU

Hráč nikdy nedostane konkrétní úkol („zabij", „zachraň", „najdi"). Vytvoř
**situaci**, ze které si úkol sám (dle archetypu většinou chybně) odvodí:

> „Nad městem už léta visí podivné ticho. Po setmění se nikdo neodváží
> ke starému hradu. Občas se z kopce ozve hluboký řev a ráno bývají pole
> rozšlapaná. Starosta slíbil odměnu každému, kdo zjistí, co se děje."

---

## P2 — VĚROHODNOST FALEŠNÝCH CEST

Falešné teorie musí mít skutečné důkazy a skutečný obsah (viz P7). Trest za
falešnou cestu nikdy nevyřazuje ze hry. Konkrétní dokončitelnost falešného
vs. skutečného řešení řídí vylosovaný archetyp (P0b).

---

## P3 — NARATIVNÍ ALIBI POHYBU

Každý fyzický úkol má důvod v ději. Nikdy „udělej 10 dřepů", vždy zarámované
(„abys přešel rozhoupanou lávku, drž rovnováhu na jedné noze a počítej do 10").
Redakční validace kontroluje, že **každý úkol má své PROČ**.

---

## P4 — KLÍČOVÉ PŘEDMĚTY: PODMÍNĚNÁ LOGIKA

Důležité artefakty se skládají z více částí, získatelných **různými cestami**:
- lehká: 2–3 komponenty · střední: 3–4 · těžká: 4–5 (u 30min profilu vždy 2).

Skutečné řešení rozprostři po větší ploše mapy než falešné lákadlo.

---

## P5 — SENZORIKA S MÍROU

Smyslové detaily dávkuj podle dramatické funkce, ne reflexivně na každé kartě.

---

## P6 — ŘETĚZCE PŘEDMĚTŮ

Předměty nesmí být osamocené klíče. Tvoř řetězce, kde předmět plodí situaci:
> hrnek → med → medvěd → kouř → peříčko → cesta ke stopě.

Povinnost dle škálovací tabulky (§SKÁLOVÁNÍ).

---

## P7 — KONKURENČNÍ FALEŠNÉ TEORIE

Počet dle škálovací tabulky. Každá falešná teorie má své „důkazy". **Jen
skutečné řešení vysvětluje VŠECHNY nalezené informace** — každá falešná
teorie aspoň jednu stopu nevysvětlí. (U A7 jsou „falešné teorie" ty skryté
konspirace, které hra podsouvá proti přímému řešení.)

---

## P8 — ŽIVÉ POSTAVY S KONFLIKTY

Každá postava má vlastní názor, motivaci a znalosti — a postavy si
**protiřečí** (lovec chce zabíjet, princezna nechce být zachráněna, kovář
chce prodat meč). Lži a zkreslení vznikají přirozeně z motivací, ne uměle.
I léčitel a obchodník jsou postavy se životem, ne servisní karty.
Počty postav a regionů dle §SKÁLOVÁNÍ.

---

## P9 — NEÚSPĚCH BAVÍ VÍC NEŽ ÚSPĚCH (zpřísněno)

Nestačí, že kostka netrestá. **Designové pravidlo: „neúspěšná" větev musí
být zábavnější než úspěšná.** Úspěch = postup; neúspěch = komedie + postup
jinudy:
> Sudá → tiše projdeš. Lichá → probudíš obra, který tě omylem považuje za
> svou ztracenou ponožku — uteč po čtyřech, ať tě nepozná.

Hráč se pak kostky nebojí, ale těší se na ni. Platí pro kostkové tabulky,
Sekce A střežených karet i následky voleb. Redakční validace to posuzuje.

---

## P10 — REGIONY MAPY

Rozděl mapu do regionů s vlastním tématem, postavami a předměty (bažina,
vodopád, severní les…). Cíl: zvědavost „co je za vodopádem?". Počty dle
§SKÁLOVÁNÍ.

---

## P11 — VRSTVY VÍTĚZSTVÍ

Konec není binární. Odstupňované konce (počet dle §SKÁLOVÁNÍ) podle toho,
kolik pravdy hráč složil a jak ji použil:
> Dobré: drak uteče. Lepší: drak a princezna odejdou spolu. Perfektní:
> přesvědčíš krále, že žádný problém nebyl.

Vrstvy vítězství jsou zároveň motor volného dojezdu: rychlí, kdo dosáhli
základního konce, mají důvod pokračovat za lepším, zatímco ostatní dojíždějí.

---

## SOCIÁLNÍ VRSTVA (parametr `format_hracu` — novinka 3.3)

Zábava na místě vzniká mezi lidmi, ne jen v hlavě. Mechaniky škáluj dle
formátu — jeden engine, tři hloubky:

| Mechanika | jednotlivci | dvojice (manželé, rodič+dítě) | týmy (max 4×4) |
|---|---|---|---|
| **Zápis teorie** (commitment) | v polovině hry herní list vyzve: „Zapiš, co si myslíš, že se děje" — payoff v epilogu | dvojice se musí shodnout na jedné teorii a podepsat ji | **sázka teorií**: tým vsadí zapsanou teorii (volitelně o body); epilog vyhodnocuje veřejně |
| **Start** | staggered (~90 s; do ~8 lidí) | staggered nebo rotovaný | **rotovaný paralelní start** — všechny týmy naráz, každý na jiném vstupu cyklu; vstupní uzly musí být dramaturgicky rovnocenné (nikdo nepřeskočí onboarding ani AHA) |
| **Role** | — | čtenář/konatel, točí se | volitelně Nositel · Sprinter · Cvičenec · Hlasatel |
| **Počítání úkolů** | čestné slovo / organizátor | navzájem | spoluhráč, role se točí |
| **Po dojezdu** | rádce (smí říct „kam se vrátit", nesmí říct „proč") | rádci | rádci + honba za vyšší vrstvou vítězství |
| **U dětí (tábor)** | prvních ~5 v cíli = oficiální rádcovská stanice | rodič moderuje | pozor na férovost mezi oddíly — stejný mix úkolů |

U věku 4–6 řeší kartu vždy dvojice dítě+dospělý.

---

## SKÁLOVÁNÍ ZÁBAVOVÉ VRSTVY (profil délky × věk)

Bohatost obsahu musí unést formát A6 a hlava cílové skupiny. Tabulka je
závazná (strojově kontrolované počty):

| Parametr | **30 min** (8–12 karet) | **60 min** (18–25) | **90 min** (25–35) |
|---|---|---|---|
| Falešné teorie (P7) | 1 | 2 | 3 |
| Pravdivé stopy (minimum) | ≥2 | ≥3 | ≥4 |
| Řetězec předmětů (P6) | volitelný, 2 články | 1× ≥3 články | 1–2× ≥3 |
| Postavy (P8) | 3–4 | 5–7 | 7–10 |
| Regiony (P10) | 1–2 | 2–3 | 3–5 |
| Konce (P11) | 2 | 2–3 | 3 |
| Komponenty artefaktu | 2 | dle obtížnosti | dle obtížnosti |
| Střežené lokace | 1–2 | 2–3 | 2–4 |
| Gated lokace | 1 | 2 | 2–3 |
| Informační uzly | ≥2 | ≥3 | ≥4 |
| Obchodník | ne | povinný | povinný |
| Inventář | 3 sloty | 5 | 5 |
| Odhad tempa | 2,5 min/kartu venku; 1,5–2 uvnitř | dtto | dtto |

**Věkový strop (má přednost):** pro věk 4–6 a 7–10 vždy max 1 falešná
teorie a 2 konce, bez ohledu na délku. Topologická minima (větve, smyčky,
slepé…) škáluj proporcionálně počtu karet; plná minima z §MAPA platí od
~20 karet.

---

## RITUÁL vs. PŘEKVAPENÍ (proti prokouknutí struktury)

Optimalizujeme na stejné hráče hrající opakovaně. Rozlišuj:

**Rituál (konstanty — snižují náklady na učení, NEMĚNIT):** onboarding
karty 1–3 · pravidla kostky · herní list · šablony karet · limit inventáře ·
epilogová ceremonie.

**Překvapení (losovat každou hru, ať struktura nejde exploatovat):**
archetyp zvratu (P0b) · práh počítadla aktivity (losuj 80–120 bodů) · počet
a umístění střežených/gated lokací v rozmezích tabulky · pozice AHA
(losuj v pásmu 65–80 % délky průchodu) · které postavy lžou · zda existuje
řetězec navíc · typ hádanky (každý skin jiný princip) · rozložení regionů.

---

## VĚKOVÁ ADAPTACE

- **4–6:** jednoduchý jazyk, pohádky, minimum abstrakce; hraje dvojice.
- **7–10:** dobrodružství, humor, jednoduché záhady.
- **11–14:** tajemství, falešné stopy, složitější logika.
- **15–18:** propracovaný svět, více vrstev.
- **dospělí:** sofistikovaný humor, sci-fi, fantasy, filozofické motivy.

---

## PROSTŘEDÍ A BANKA ÚKOLŮ (parametr `prostredi`)

Úkoly čerpej z banky filtrované štítkem prostředí + kategorií
(pohyb/zvuk/hlava/grimasy) + intenzitou:

| Štítek | Povoleno | Zakázáno |
|---|---|---|
| `les` (reference) | křik, běh, terén, přírodní rekvizity | nebezpečný terén, skoky z výšky |
| `chalupa_zahrada` | běh, mírný hluk, domácí předměty | cizí pozemky |
| `byt` | tiché fyzické (výpony, plank, rovnováha) | dupání, křik |
| `hotel` | tichý režim: chůze „jako agent", rovnováha, paměť, grimasy | křik na chodbě, běh po schodech |

Kostkové tabulky se skládají už z filtrovaných úkolů. Balanc košíku: každý
hráč/tým dostane podobný MIX kategorií (nikdo jen zpěv, jiný jen dřepy).

## FYZICKÉ ÚKOLY — `physical_intensity`

- **`low` (default 4–14, rodina, teambuilding):** rovnováha, koordinace,
  pozorování, paměť, napodobování, krátké výzvy. Zakázané: angličáky,
  burpees, horolezci, sprinty, dlouhé běhy.
- **`high` (volitelně 15+):** dřepy, výskoky, výpady, běh na místě — vždy
  s alibi (P3) a vždy s alternativou pro toho, kdo nemůže cvičit.

Pohyb primárně garantují **přeběhy mezi uzly** (křížové hrany s příběhovým
důvodem) — ty platí vždy; intenzita úkolů je parametr. Nikdy nic
nebezpečného v neznámém terénu.

---

## SLOVNÍK ŽÁNRU (před kartami)

`allowed_terms[]`, `forbidden_terms[]`, `replacement_map{}`. Zakázané slovo
se nikdy nepoužije; únik se nahradí a zaznamená.

---

## ONBOARDING (karty 1–3)

Učí: pohyb po mapě, inventář, kostku. Bez útěku, trestu, hrozby. (U archetypu
A5 smí onboarding obsahovat bezelstnou akci, která se později ukáže jako
příčina — ale v momentě hraní působí nevinně.)

---

## MAPA A TOPOLOGIE

Nelineární: hlavní trasa, vedlejší větve, smyčky, slepé uličky, jednosměrné
události (předem signalizované), ≥2 alternativní cesty ke klíčovým
komponentám, opakované návraty. **Nikdy softlock.** Plná minima (≥3 větve,
≥2 smyčky, ≥2 slepé, ≥2 jednosměrky) od ~20 karet, menší hry proporcionálně.

Typy uzlů: `onboarding, rozcesti, sber, prechod, slepa, jednosmer, smycka,
strez, gated, informace, postava, lecitel, obchodnik, cil`.

**Obchodník (nový typ):** výměna předmětů 1:1, jistí nevratné oběti batohu
(prakticky brání „měkkému softlocku" ze zahozené věci). Povinný u 60/90min
profilů. Je to postava s motivací (P8), ne automat.

**Slepé cesty krátké:** u profilů ≤60 min max 1 uzel hloubky, návrat hned.
Frustrace se generuje kolapsem teorie u cíle, ne blouděním. Dlouhé nadějné
slepé větve jen u 90min/těžká.

Rytmus: žádné dvě `sber` karty za sebou; nikdy 2–3 čistě běhací uzly po
sobě — proložit oddechem (čtení, hádanka, rozhodnutí). Topologické poměry
(~30 % návratových, ~15 % jednosměrných, ~20 % informačních, ~20 % slepých)
orientačně od 20 karet.

## ROZCESTÍ

Volby vytvářejí **nové informace**, ne jen delší cestu. **Zákaz prázdných
voleb** (strojově validováno): žádná karta nesmí mít dvě volby se shodným
cílem i shodným efektem.

## OPAKOVANÉ NÁVŠTĚVY (paměť světa — střední/těžká)

Karta má podmíněný řádek („Máš LUCERNU? čti dolní odstavec"). Svět si
pamatuje pokrok.

## GATING

Uzamčené lokace, na které hráč opakovaně naráží. Nikdy jediná cesta
k povinné komponentě.

## FYZICKÝ BYPASS (limitovaně)

Na max 2 střežených lokacích za hru smí Sekce A nabídnout překonání
překážky fyzickým úkolem. **Bypass dává průchod, NIKDY klíčovou
komponentu** (jinak se rozbije ekonomika předmětů) a nikdy nesmí obcházet
lokaci střežící AHA odhalení.

## INFORMACE JSOU ODMĚNA

Uzel `informace` dává stopu s pravdivostní hodnotou: **pravda** /
**zavádějící** / **lež** (lži živí falešné teorie a plynou z motivací
postav, P8). Minima pravdivých stop dle §SKÁLOVÁNÍ; pravdivé stopy
dohromady MUSÍ stačit k odvození řešení, ale žádná sama o sobě.

---

## INVENTÁŘ

Limit dle profilu (3/5/5). Věci z přírody/chaty. ~60 % užitečných / ~40 %
atrap (atrapy živí falešné teorie, nikdy neblokují). Každý předmět: název ·
co dělá · jak se používá · omezení. Přidává se jen na zadní straně karty:
„Přidáno do inventáře: [Název] — …".

## STAVY

Zmatený, unavený, ulekaný, pokousaný, prokletý. Nikdy nevyřadí; vždy
léčitelné (`lecitel`).

## KOSTKA

Šestistěnná. Dvě formy: (a) sudá/lichá či 1–3/4–6 na běžných kartách
(~30 % karet), (b) **kostková tabulka 1–6** na `sber`/`prechod` uzlech —
šest různých mikroúkolů z filtrované banky; dává papíru variabilitu při
opakovaných průchodech. Výsledek nikdy nevyřazuje a řídí se P9 (neúspěch
baví víc).

## SYSTÉM NÁPOVĚDY

Na herním listu **počítadlo fyzické aktivity**; po dosažení prahu
(losováno 80–120 bodů) smí hráč navštívit postavu nápovědy (1–2 v mapě).
Rada posune, nikdy neprozradí řešení. V konceptu urči bodování úkolů tak,
aby průměrný hráč dosáhl prahu kolem 2/3 hry.

---

## ŠABLONY KARET

**Běžná karta (A6):**
```
[ČÍSLO] [NÁZEV]
Příběh 2–4 věty (u starších bohatší). Smyslový detail dle P5.
Vyberte akci:
A) akce + herní důvod → karta X
B) akce + herní důvod → karta Y
[volitelně: kostka / podmínka předmětu / stav]
Po volbě otoč kartu.
```
Zadní strana: 2–4 věty výsledku; „Přidáno do inventáře: …"; každá větev
končí „→ karta X".

**Střežená karta:** [PŘEDNÍ] příběh + „Máš A i B?" NE→Sekce A, ANO→Sekce B.
[ZADNÍ] Sekce A: komplikace/bypass/návrat — zábavnější než úspěch (P9),
vždy s pokračováním. Sekce B: kostka a odměna.

**Cílová karta (nová šablona):** [PŘEDNÍ] finální scéna + otázka na klíčové
poznání („Víš, proč se drak vrací k louce?" / „Máš [komponenty]?").
[ZADNÍ] sekce konců dle P11: podmínky každé vrstvy vítězství + odkaz
„organizátor nyní přečte epilog". Vše se musí vejít na A6 — konce piš
telegraficky.

---

## EPILOGOVÁ CEREMONIE (povinná součást průvodce)

Konec rozhoduje o vzpomínce na celou hru (peak-end). Průvodce organizátora
obsahuje **epilog k přečtení nahlas všem** po dojezdu:
1. Celý skutečný příběh (co se doopravdy dělo).
2. Mapa lží: kdo lhal, proč, a které stopy byly pravdivé.
3. Vyhodnocení zapsaných teorií/sázek (formát dvojice a týmy) — veřejně,
   s humorem, bez ponižování.
4. Vyhlášení: dosažené vrstvy vítězství, diplomy (nejvíc dřepů, nejlepší
   grimasa, nejodvážnější teorie…).

Epilog zajistí kolektivní AHA i hráčům, kteří pravdu nesložili — místo
zmatku odejdou se smíchem nad vlastní slepou uličkou.

---

## HUMOR

Absurdní situace, nečekané následky, komické postavy — přiměřeně věku a
tónu. Humor koncentruj do neúspěšných větví (P9).

---

## GENEROVÁNÍ — FÁZE

**FÁZE 0 — LOSOVÁNÍ:** přečti registr, vylosuj archetyp zvratu a parametry
z §RITUÁL vs. PŘEKVAPENÍ. Zapiš do konceptu.

**FÁZE 1 — ARCHITEKT:** struktura mapy jako DATA (uzly, typy, hrany,
regiony, závislosti komponent), škálovaná dle profilu délky.

**FÁZE 2 — NARATIVNÍ DESIGNÉR:** úvod bez úkolu (P1), zápletka dle
archetypu, falešné teorie s důkazy, AHA odhalení, skutečné řešení, slovník
žánru, rozvržení stop (pravda/zavádějící/lež) a postav s konflikty, návrh
epilogu, bodování počítadla aktivity.

**FÁZE 3 — UX DESIGNÉR:** všechny karty dle šablon (vč. cílové karty a
herního listu se zápisem teorie dle formátu hráčů), onboarding, střežené,
postavy, léčitel, obchodník (60/90).

**FÁZE 4 — QA (spustí KÓD + redakce):** viz VALIDACE. Při chybě oprav a
přegeneruj.

**FÁZE 5 — ART DIRECTOR (jen při `ilustrace: true`):** pro klíčové lokace,
postavy a předměty vygeneruj neutrální anglické popisy pro AI generátor
obrázků do `prompty_ilustrace.md` (Formát: [Název] – [popis, atmosféra,
styl]).

---

## VALIDACE — DVĚ PATRA (poctivé rozdělení)

### Patro 1 — STROJOVÁ (spustitelný kód nad grafem `{uzel: (typ, [hrany])}`)

1. **Dosažitelnost:** cíl dosažitelný ze startu; žádný osiřelý uzel.
2. **Žádný softlock:** každý uzel (kromě `cil`) má východ; `smycka`,
   `slepa`, `jednosmer` mají garantovaný návrat.
3. **Rytmus:** žádné dvě `sber` za sebou.
4. **Prázdné volby:** žádná karta se dvěma volbami se shodným cílem
   i efektem.
5. **Škálovací počty:** vše dle tabulky §SKÁLOVÁNÍ (teorie, stopy, postavy,
   regiony, konce, střežené, gated, informační, obchodník, inventář) +
   topologická minima proporcionálně.
6. **Dokončitelnost dle archetypu:** A1–A6 — žádná cesta nedokončí ŽÁDNÉ
   falešné řešení a všechna falešná lákadla jsou složitelná; skutečné řešení
   dokončitelné s kompletní sadou komponent. A7 — přímé řešení dokončitelné,
   netriviální (≥2 komponenty/podmínky).
7. **Komponenty:** počty dle obtížnosti/profilu; každá dosažitelná ≥2
   cestami; gated nikdy jediná cesta k povinné komponentě.
8. **Inventář:** limit dle profilu; ~60/40; plné popisy; věta „Přidáno…".
9. **Kostka:** ~30 % karet; tabulky 1–6 na sber/prechod; nic nevyřazuje.
10. **Slovník:** žádné `forbidden_terms`.
11. **Bezpečnost:** úkoly dle `physical_intensity`, věku a prostředí
    (štítky); `low` bez zakázaných cviků; hotel bez křiku a běhu po schodech.
12. **Délka a dramaturgie:** ≥5 simulovaných průchodů; medián odpovídá
    profilu (2,5 min/kartu venku, 1,5–2 uvnitř); **pozice AHA odhalení
    v 65–80 % mediánového průchodu**; onboarding karty 1–3 bez
    trestu/hrozby.
13. **Bypass:** max 2, žádný nedává komponentu, žádný neobchází AHA lokaci.

### Patro 2 — REDAKČNÍ (LLM posudek s rubrikou; každý verdikt MUSÍ citovat
konkrétní karty jako důkaz — bez citace je verdikt neplatný)

R1. **Pravda se odvozuje:** žádný jednotlivý uzel neprozrazuje řešení;
    existují ≥2 nezávislé stopy, jejichž průnik k němu vede. Cituj stopy.
R2. **Konkurenční teorie:** každá falešná teorie má důkazy a aspoň jednu
    nevysvětlenou stopu; jen řešení vysvětluje vše. Cituj.
R3. **Postavy:** konflikty a protiřečení existují; lži plynou z motivací.
R4. **P9:** neúspěšné větve jsou zábavnější než úspěšné (namátkou 5 karet).
R5. **Alibi:** každý fyzický úkol má své PROČ (projdi všechny úkoly).
R6. **Věk a tón:** jazyk odpovídá věku; humor přiměřený.
R7. **Metahra:** srovnej s registrem — nepůsobí hra jako kopie předchozích?

**Simulace:** ≥5 náhodných průchodů (inventář, komponenty, stavy, skryté
sekce, cíl); edge-case (chybějící předmět, pokus o falešné řešení, počítadlo
pod/nad prahem); simulovaný playtest 2 hráčů (falešná teorie zabrala?
plynulost? frustrace?).

Výstup: `validation_report` (strojové checky), `editorial_report` (R1–R7
s citacemi), `simulation_reports`, `playtest_feedback`. Jedna vadná karta
neshazuje balíček — oprav a přegeneruj.

---

## POSTUP PŘI SPUŠTĚNÍ (Cowork)

1. Přečti/založ `skiny/registr.md`; založ `skiny/<nazev-skinu>/`.
2. FÁZE 0–2: ulož `koncept.md` (archetyp, mapa, teorie, řešení, slovník,
   epilog, bodování aktivity, losované parametry).
3. FÁZE 3: naplň `generator_template.py`, spusť → `*_karty.pdf`.
4. FÁZE 4: spusť `validace.py` + redakční posudek; opravuj do čista.
5. Vygeneruj `*_pruvodce.pdf`: mapa s vítěznou cestou (a cestami všech
   konců), **epilog k přečtení**, **stavěcí checklist** (obhlídka 5 min →
   mapování uzlů na místa 5 min → rozmístění 5 min → brífink 1 min,
   doslovné znění), obsah všech karet (náhrada za ztracenou), pokyn kdy
   zasáhnout (nikdo neodhalil v 80 % času → postava nápovědy přijde sama),
   pravidla pro rádce, QA + redakční report, tisková instrukce,
   **feedback formulář** (5 otázek: V kolikáté minutě padlo AHA? Kde se
   zasekli? Čemu se nejvíc smáli? Co bylo moc těžké/lehké? Hráli by znovu?).
6. Aktualizuj `skiny/registr.md` (archetyp, mechanismus řešení, rekvizity,
   žánr, skupina). Vyplněné feedback formuláře ukládej jako
   `skiny/<skin>/playtest_vysledky.md` — při dalším generování je čti a
   kalibruj obtížnost misdirection.
7. Vypiš uživateli shrnutí + odkazy + reporty.

---

## VÝSTUPNÍ FORMÁT

**(A) Tisknutelné karty** — A6, 4 na A4, čáry na střih, barevné typy uzlů,
oddělené přední/zadní strany střežených a cílové karty, herní list
(inventář, počítadlo aktivity, pole „moje teorie", sběr) dle formátu hráčů.
**(B) Strojový JSON** — cards[], concept, glossary, validation_report,
editorial_report, simulation_reports, playtest_feedback, errors[].

---

## KRITÉRIA HOTOVÉ HRY

✓ registr přečten a aktualizován · ✓ archetyp vylosován (žádné opakování
z posledních 3) · ✓ úvod bez úkolu · ✓ AHA odhalení v 65–80 % průchodu ·
✓ pravda se odvozuje průnikem stop · ✓ teorie/stopy/postavy/regiony/konce
dle škálovací tabulky · ✓ falešná lákadla složitelná, dokončitelnost dle
archetypu · ✓ sociální vrstva dle formátu hráčů (zápis teorie / sázka) ·
✓ epilog v průvodci · ✓ neúspěch baví víc než úspěch · ✓ žádný softlock ·
✓ žádné prázdné volby · ✓ úkoly dle věku, intenzity a prostředí · ✓ bypass
limitovaný · ✓ stavěcí checklist + feedback formulář v průvodci ·
✓ délka odpovídá profilu (simulace) · ✓ strojová i redakční validace čisté.
