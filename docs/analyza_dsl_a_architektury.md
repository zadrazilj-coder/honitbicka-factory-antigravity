# Analýza: struktura hry jako DSL (Twine/ink/Arcweave) a co bych udělal jinak

> Zadání revize (2026-07-05): projít detailně honbicka-factory a kriticky posoudit,
> zda by převzetí struktury z nástrojů typu Twine, Arcweave, articy:draft nebo ink
> vedlo ke zjednodušení/zpřehlednění; zda existuje lepší algoritmus; a co má smysl
> dělat na lokálním modelu vs. předat frontier modelům. Zapsat všechna zjištění.

---

## 1 · Shrnutí (TL;DR)

1. **Nástroje Twine/Arcweave/articy:draft NEadoptovat** — jsou to GUI editory pro
   člověka, ne pro autonomní továrnu. **Adoptovat ale jejich klíčový princip:
   volba je DATA (cíl + podmínka + text), ne próza.** Dnes struktura hry žije
   dvakrát (graf v `mapa.json` + šipky „→N" v próze karet) a celá třída chyb
   a oprav (O1, SC3, regex `_SIPKA_CISLO`, `_oprav_volby_deterministicky`)
   existuje jen kvůli této duplicitě. Viz §3 — včetně živého důkazu, že
   regex-validace má díru.
2. **ink jako runtime/formát nepřebírat** (tisková hra s přední/zadní stranou,
   CORE/SIDE párem 30/60 a A5 fit-checkem se do ink modelu nevejde), ale
   **jednosměrný export do `.twee` / Mermaid přidat** — levné (~50 řádků),
   splní požadavek „lze snadno zkontrolovat": .twee soubor se dá přetáhnout do
   Twine a hra se okamžitě zobrazí jako klikatelný graf.
3. **Lepší algoritmy existují a sedí přesně na zdejší problémy:**
   graf-gramatiky nebo ASP (clingo) pro topologickou variabilitu (SC2),
   analytický výpočet očekávané pozice AHA (absorbující Markovův řetězec)
   místo Monte Carlo mediánu (řeší třídu 180/3600 edge-case selhání),
   embeddings pro okna zákazů v registru.
4. **Dělba lokální/frontier:** lokální 27B model je správně na kartách a tématech
   (levné, dávkové, soukromé), ale prokazatelně selhává na (a) globální
   narativní soudržnosti, (b) topologii (nekonvergence, viz rozhodnuti.md M8),
   (c) češtině („tlaký", „Strážek", „nožnicemi", „plže po zádech" — živá data).
   Frontier model nasadit na **koncept/story-bible, redakci R1–R7 a finální
   jazykovou korekturu** — na jednu hru je to ~3 volání, tedy jednotky Kč.
5. **Co rozhodně zachovat:** zásadu „LLM tvoří, Python rozhoduje",
   deterministický scaffolder, reálný render fit-check, ověřování citací
   redaktora grepem, seed-reprodukovatelnost, registr, decision log a testovací
   disciplínu. Architektura je nadprůměrně poctivá; problém není „špatný
   program", ale dvě konkrétní designová rozhodnutí (IR karet, jedna pevná
   kostra) a přetěžování malého modelu úlohami, na které nestačí.

---

## 2 · Co je dnes dobře (a v přepisu se NEMÁ ztratit)

- **„LLM tvoří, Python rozhoduje"** — důsledně dodrženo; všechny herní
  invarianty validuje deterministický kód. Tohle je vzácně čistý řez.
- **Deterministický scaffolder** po empiricky doloženém zjištění, že 27B model
  topologické invarianty nesplní (93 min, 12 iterací, nikdy 0 chyb) — správná
  reakce, správně zdokumentovaná.
- **Fit-check reálným renderem** (WeasyPrint), ne odhadem znaků; fail-fast bez
  GTK před prvním LLM voláním.
- **Redaktor s ověřenými citacemi** — LLM-judge, jehož verdikt bez doslovné
  citace neplatí, je dobrý vzor proti halucinaci posudku.
- **Reprodukovatelnost** (seed v reportu i registru), append-only registr,
  `docs/rozhodnuti.md` jako decision log, 244 rychlých testů bez GPU/GTK.
- Pár 30/60 přes CORE/SIDE podgraf — elegantní: jedna validace běží na obou.

---

## 3 · Klíčové zjištění: struktura hry žije dvakrát

Graf je v `mapa.json` (uzly + hrany), ale **navigace, kterou hráč skutečně
čte, je zapečená v próze** polí `predni`/`zadni` jako „A) text →N". Z této
duplicity plyne celý aparát: regex `_SIPKA_CISLO`, `_volby_v_karte_platne`,
opravné prompty `oprava_voleb`, `_oprav_volby_deterministicky`,
`volby_neopravitelne` v reportu, a synchronizace názvů SC3.

**Živé důkazy z `skiny/ctyri-svetla/karty.json`** (běh 2026-07-04, částečně
před opravou O1 — ale díra v regexu platí dodnes):

- **Karta 9 (slepa):** volby „A) … **→ slepa 10** B) … **→ slepa 11**
  C) … **→ slepa 12** D) … → 7". Regex `→\s*(\d+)` vyžaduje číslici hned za
  šipkou → tři ze čtyř voleb **vůbec nevidí**, najde jen `{7}` ⊆ hrany `{7}`
  a validace **projde**. Vytištěná karta přitom posílá hráče na cíle, které
  graf nezná. Tohle není opravitelné lepším regexem — je to důsledek toho,
  že volby jsou text.
- **Karta 3 (informace):** čtyři volby A–D, všechny „→5". Graf má jednu hranu
  3→5, takže kontrola hran projde; engine pravidlo „zákaz prázdných voleb"
  (shodný cíl i efekt) se ale kontroluje jen nad `Hrana.efekt` v grafu —
  próza si může vyrobit libovolný počet pseudovoleb se stejným cílem a
  validátor to nevidí.
- **Karta 6 (gated):** „→6A", „→6B" — regex z toho vytáhne `6` (sebeodkaz);
  dnes by to O1 chytil, ale jen proto, že náhodou začíná číslicí. „→ sekce B"
  by neviděl.
- **Karta 8:** „Návrat na začátek (→11 smyčka 11)" — validní číslo, zmatečná
  instrukce; kvalitu navigační věty nikdo nekontroluje, protože věta JE
  nosičem navigace.

**Návrh (jádro celé revize): volby jako strukturovaná data.**

```python
class Volba(BaseModel):
    pismeno: str          # doplňuje Python, ne LLM
    text: str             # „Přistoupit k blikající lampě" — JEN akce, bez šipky
    vysledek: str         # text na zadní straně pro tuto volbu
    cil: int              # doplňuje/vynucuje Python z Hrany
    podminka: str | None  # zrcadlí Hrana.podminka

class Karta(BaseModel):
    cislo: int
    atmosfera: str
    uvod: str             # příběhový odstavec přední strany (bez voleb)
    volby: list[Volba]    # 1:1 s uzel.hrany — vynuceno schématem
    zadni_30_filtr: ...   # 30min varianta = deterministický filtr SIDE voleb
```

Řádek „A) text → karta N" pak **skládá renderer**, ne LLM. Důsledky:

- třída chyb O1 zaniká *z konstrukce* (LLM šipku nikdy nepíše),
- `zadni_30` varianta je deterministický filtr voleb, ne druhý LLM text
  (dnes model píše obě zadní strany a mohou se rozjet),
- „prázdné volby" jdou kontrolovat i na úrovni textu (shodný cíl + shodný
  `vysledek`),
- redakční grep i průvodce čtou strukturu, ne prózu,
- structured output Ollamy tohle schéma vynutí stejně spolehlivě jako dnešní
  ploché `predni`/`zadni`.

Toto je přesně to, co dělá ink (`* volba -> cíl`) a Twine (`[[text->Cíl]]`) —
jen bez adopce jejich runtime. **Odpověď na otázku „zjednodušilo by to
program?": ano, ale stačí převzít princip, ne nástroj.**

---

## 4 · Porovnání s konkrétními nástroji

| Nástroj | Co je zač | Co by dal | Proč ne (jako základ) |
|---|---|---|---|
| **ink (Inky/inklecate)** | textový jazyk + kompilátor + JSON runtime | čitelný zdroják celé hry v 1 souboru; compile-time kontrola visících diverts; hotový runtime pro simulaci | model „obrazovkové" hry: nezná fyzické karty (přední/zadní strana, A5 fit), pár 30/60, pozici AHA v čase, škálovací tabulku — 90 % zdejších validátorů by zůstalo stejně; přibyla by závislost (inklecate je .NET) |
| **Twine / twee** | GUI editor + prostý textový formát pasáží `[[link]]` | okamžitá vizualizace grafu (drag&drop .twee do Twine); triviální export | makra (Harlowe/SugarCube) jsou pro strojovou validaci horší než dnešní pydantic graf; cílí na HTML hraní, ne tisk |
| **Arcweave** | komerční webové GUI, JSON export | hezká vizualizace, spolupráce | uzavřené, online, neautomatizovatelné lokálně — proti podstatě „autonomní továrny na lokálním HW" |
| **articy:draft** | těžký komerční Windows nástroj (herní studia) | silný datový model postav/entit | licence, GUI-first, žádná cesta k autonomnímu batch generování |

**Verdikt:** dnešní `Mapa`/`Uzel`/`Hrana` (pydantic + JSON) je pro *strojovou*
továrnu lepší reprezentace než kterýkoli z těch nástrojů — je typovaná,
validovatelná, diffovatelná. Co chybí, není jiný nástroj, ale:

1. **volby jako data** (§3) — princip ink/Twine,
2. **lidsky čitelný pohled** — a ten se dá koupit za ~50 řádků exportu:

```
:: 7 Rozcestí u lamp {"position":"…"}
Stojíš před čtyřmi zářícími paprsky…
[[Modré světlo->10 Postava]]
[[Červené světlo->9 Slepá]]
```

Doporučení: `honbicka export <slug> --format twee|mermaid|dot`.
Mermaid blok navíc patří přímo do průvodce organizátora (mapa hry) a do
`INDEX.md`. Tím se splní požadavek „program lze snadno zkontrolovat" —
člověk hru proklikne v Twine, aniž by četl JSON.

---

## 5 · Jiné algoritmy, které by pomohly

### 5.1 · Topologie: graf-gramatiky nebo ASP místo jedné pevné kostry

Dnešní scaffolder = 1 ručně vyladěný 21-uzlový vzor. SC2 (variabilita) je
odloženo, protože každá ruční změna kostry vyžaduje přehrát celou ověřovací
mřížku (3600 kombinací). To je symptom špatného směru: **vzory se nemají
ručně kreslit, mají se generovat z pravidel.**

- **Graf-gramatiky (mission grammars, Dormans):** startovní osa
  `start → … → cíl` + přepisovací pravidla („vlož smyčku", „přidej slepou
  větev hloubky 1", „obal komponentu gated uzlem", „připoj SIDE region se
  vstupem před dominátor X"). Každé pravidlo zachovává invarianty
  (souvislost, návratnost) → výsledek je validní *z konstrukce* jako dnes,
  ale seed × pravidla = stovky různých topologií. Validační mřížka se pak
  spouští na generátor pravidel, ne na každý ručně přidaný vzor.
- **ASP / clingo (answer set programming):** Patro 1 je už teď formální
  seznam omezení — dá se přepsat 1:1 do clinga (dosažitelnost, dominátory,
  počty typů, minima větví/smyček) a nechat solver **enumerovat** validní
  grafy pro daný seed. Clingo je malá lokální závislost, řeší 21–35 uzlů
  v milisekundách. Nejčistší možná realizace „Python rozhoduje".
- Pragmatické minimum (bez nové závislosti): začít u SIDE regionu, jak už
  navrhuje rozhodnuti.md — gramatika jen pro SIDE, CORE nechat.

### 5.2 · Pozice AHA: analyticky, ne Monte Carlo

`_vyber_aha_uzel` dnes běží 15 náhodných průchodů na kandidáta a bere medián
— odtud šum, dřívější bug 5-vs-15 průchodů i třída 180/3600 selhání
(A1 + konkrétní seedy → AHA v 82–88 %). Náhodná procházka s pevnými vahami
je **Markovův řetězec s absorbujícím stavem (cíl)**: očekávaný čas návštěvy
uzlu i očekávaná délka průchodu se dají spočítat **přesně** soustavou
lineárních rovnic (fundamentální matice, `numpy.linalg.solve`, 21×21 — okamžité).
Pravidlo první návštěvy (40% tempo) proces komplikuje (není čistě markovský),
ale i tam stačí aproximace prvního řádu: čas první návštěvy počítat přesně,
opakované návštěvy penalizovat očekávaným počtem návratů. Výsledek:
deterministická, hladká funkce `pozice_aha(uzel)` → výběr uzlu bez šumu,
edge-case třída zaniká, simulace zůstane jen jako sanity check.

### 5.3 · Registr: sémantická deduplikace

Okna zákazů porovnávají přesné řetězce (`mechanismus.lower()`). Po O5 je to
lepší než tokeny, ale „Drak kýchá kvůli pylu" vs. „Saň má alergii na květinu"
projde jako dvě různé hry. Ollama umí lokálně embeddings
(`nomic-embed-text`, ~30 ms/větu): ukládat do registru vektor mechanismu a
zakazovat kosinovou podobnost > ~0.8 proti posledním N hrám. Malý zásah,
registr začne dělat to, co slibuje.

### 5.4 · Drobné

- `povinne_uzly` je O(N·(N+E)) BFS-bez-uzlu — pro ≤35 uzlů v pořádku;
  kdyby se přešlo na gramatiky s většími grafy, Lengauer–Tarjan dominator
  tree je přímočará náhrada. Neřešit teď.
- Simulace ignoruje `Hrana.podminka`/inventář (V2/V3 v auditu) — jakmile
  gramatika začne podmínky reálně osazovat, průchod musí sbírat komponenty;
  jinak délka i AHA % lžou. Patří do stejného balíku jako 5.1.

---

## 6 · Lokální model vs. frontier modely

### Co lokální model (qwen3.6:27b) prokazatelně umí a má dělat dál

- **Texty jednotlivých karet** s úzkým strukturovaným schématem — funguje,
  levné, přes noc, žádná data neopouštějí stroj.
- **Téma-generátor** (krátký výstup, vysoká teplota) — funguje (~29 s).
- **Objem/dávka:** desítky her za noc je přesně use-case lokálního HW.

### Kde lokální model prokazatelně selhává (důkazy v repu)

1. **Topologie:** nekonverguje (rozhodnuti.md, M8) — už vyřešeno scaffolderem.
2. **Globální narativní soudržnost:** karty „čtyř světel" jsou atmosférické,
   ale nespojité (zrcadla/panely/lampy bez vztahu); AHA na kartě 8 vyzní jako
   dialogová vata. O3 (koncept do promptu) pomůže, ale per-karta volání s
   ~1,5k tokeny kontextu principiálně nemůže držet klubko stop, které se má
   protnout až v 70 % hry. **Tohle je úloha pro model, který udrží celou hru
   v jednom kontextu.**
3. **Čeština:** živá data obsahují „tlaký vzduch", „Strážek", „plže po
   zádech", „Větrný mlátění", „utonut ve tmě", „nožnicemi", „uvolnící",
   „rozsvitu" — u produktu, kde text JE produkt (čtou ho děti 9–12 nahlas),
   je to diskvalifikační vada, kterou žádný dnešní validátor nevidí.
4. **Koncept:** živě vracel tokeny („prunik_stop", prázdná rekvizita —
   viditelné dodnes v `skiny/ctyri-svetla/koncept.md` a v registru); O5 to
   záplatoval validátory a mechanickou opravou, ale kvalita zápletky zůstává
   nejslabším článkem — a přitom je to kreativní srdce hry.

### Doporučená dělba (hybridní pipeline)

| Fáze | Kdo | Proč |
|---|---|---|
| FÁZE 0 losování, topologie, validace, sazba | Python | beze změny |
| **FÁZE 2a — story bible** (nové): zápletka, falešné teorie s důkazy, per-uzel narativní beaty (kdo lže a proč, kde je která stopa, řetězec předmětů), epilog | **frontier** (1 dlouhé volání) | jediná úloha vyžadující globální úvahu; dnes neexistuje a její absence je příčina O3 i chudého R1/R2 |
| FÁZE 3 — texty karet z beatů | lokální | beat říká „co", model píše „jak" — přesně jeho liga |
| **FÁZE 4a — redakce R1–R7** | **frontier** (1 volání, celá hra v kontextu) | posudek průniku stop vyžaduje vidět všechno; dnešní vzorkování 4+N karet je kompromis vynucený malým modelem |
| **FÁZE 4b — jazyková korektura** (nové) | **frontier** (1 volání, diff-style opravy) | odstraní „tlaký/Strážek" třídu chyb; deterministicky ověřit, že se nezměnila čísla voleb ani struktura |
| Registr embeddings | lokální (nomic-embed) | §5.3 |

Cena: ~3 frontier volání na hru (řádově desítky tisíc tokenů) — u Claude
Haiku/Sonnet jednotky Kč za hru; dávka 30 her za noc ≈ cena jedné pizzy.
Návrh rozhraní: `LLMKlient` protokol se dvěma implementacemi
(`OllamaKlient`, `AnthropicKlient`) a mapování rolí → klient v configu;
offline režim = vše na Ollamu (dnešní chování zůstane jako fallback).
Story bible je čistě aditivní artefakt (`story_bible.json` ve skinu) —
zapadá do dnešního toku bez přestavby.

### Co dělat frontier modelem jednorázově (ne za běhu)

- návrh knihovny gramatických pravidel / druhé SIDE kostry (§5.1),
- few-shot příklady pro vypravěče (2–3 vzorové karty na žánr),
- banka úkolů dle prostředí (engine ji předepisuje, dnes nemodelována — O12).

---

## 7 · Kdybych to stavěl znovu — cílová podoba

Pipeline by zůstala (FÁZE 0–5, stavový stroj, validátory), změnily by se
tři věci:

1. **Jedna reprezentace hry.** `hra.json` = uzly nesoucí strukturu I obsah;
   `Volba` jako data (§3); `mapa.json`+`karty.json`+`koncept.md` jsou dnes
   tři soubory, které se musí synchronizovat (SC3 je toho symptom).
   Z jedné reprezentace se deterministicky renderují: PDF, průvodce,
   .twee/Mermaid export, blob pro redaktora.
2. **Topologie z pravidel, ne ze vzoru** (§5.1) + analytická pozice AHA (§5.2).
3. **Story bible mezi konceptem a kartami** (§6) — nejen kvůli kvalitě:
   teprve s per-uzel beaty („uzel 4 = lež pastýře podporující teorii B")
   dostanou R1/R2 a minima pravdivých stop skutečnou datovou oporu
   (dnes je `pravdivost` jen na 3 INFORMACE uzlech — viz MD2 v rozhodnuti.md).

Co bych NEdělal: nepřepisoval bych na cizí runtime (ink), neměnil pydantic
za nic „chytřejšího", nerušil scaffolder ve prospěch LLM architekta a
nepouštěl se do 90min profilu, dokud nefunguje variabilita 30/60.

---

## 8 · Seznam doporučení (seřazeno podle poměru přínos/riziko)

| # | Doporučení | Přínos | Náročnost |
|---|---|---|---|
| 1 | **Volby jako strukturovaná data** (`Volba` model, renderer skládá „A) … → N") | zaniká třída O1 vč. prokázané díry v regexu (karta 9); čistší 30/60 varianty; kontrola prázdných voleb i na textu | střední (modely + prompt vypravěče + sazba; validátory se zjednoduší) |
| 2 | **Export .twee + Mermaid** (`honbicka export`) | lidská kontrola hry proklikem v Twine; mapa do průvodce | nízká (~50–80 řádků, jen čtení dat) |
| 3 | **Frontier korektura češtiny** (FÁZE 4b) | odstraní jazykové vady, které dnes nevidí žádný validátor | nízká (1 volání + deterministický diff-check) |
| 4 | **Story bible frontier modelem** (FÁZE 2a) + karty lokálně z beatů | největší páka na kvalitu obsahu (řeší kořen O3); datová opora pro R1/R2 | střední |
| 5 | **Analytická pozice AHA** (absorbující Markovův řetězec) | deterministický výběr AHA uzlu, konec 180/3600 edge-case třídy | nízká–střední (jedna funkce + testy proti simulaci) |
| 6 | **Redakce R1–R7 frontier modelem** (celá hra v kontextu) | poctivý posudek místo vzorkování; citace dál ověřovat grepem | nízká (jen routing role) |
| 7 | **Graf-gramatika / ASP pro topologii** (začít SIDE regionem) | skutečné řešení SC2 (variabilita) místo ručních vzorů | vysoká (ale nahrazuje ještě dražší ruční cestu z rozhodnuti.md) |
| 8 | **Embeddings v registru** (nomic-embed přes Ollamu) | okna zákazů začnou fungovat sémanticky | nízká |
| 9 | Sloučit reprezentaci do jednoho `hra.json` (po #1) | konec synchronizací mapa↔karty↔koncept | střední |
| 10 | Neadoptovat Twine/Arcweave/articy/ink jako základ | — (rozhodnutí, ne práce) | — |

Pozn.: nálezy z tohoto rozboru, které jsou čistě bug-charakteru (díra regexu
u nečíselných šipek; prázdné volby existující jen v próze), řeší doporučení
#1 z konstrukce — samostatná záplata regexu má smysl jen pokud se #1 odloží.
