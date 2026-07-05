# Návrhy vylepšení — audit kódu HONBIČKA FACTORY

> Průběžně zapisovaný audit celého kódu (2026-07-04). Tři osy:
> **M** = mechanismus (architektura/logika) · **R** = rychlost (výkon) ·
> **S** = správnost popisů (docstringy, komentáře, prompty vs. realita).
> Priorita: 🔴 vysoká · 🟡 střední · 🟢 nízká (nice-to-have).

**Stav auditu:** DOKONČENO 2026-07-04.

- [x] honbicka/llm.py
- [x] honbicka/modely.py
- [x] honbicka/orchestrator.py
- [x] honbicka/scaffold.py
- [x] honbicka/validatory/ (topologie, skalovani, simulace, sazba, agregace)
- [x] honbicka/sazba/ (render, styl, karty_pdf, herni_list, pruvodce, karta_html)
- [x] honbicka/registr.py + taxonomie.py
- [x] honbicka/davka.py + feedback.py + cli.py
- [x] tests/ (mezery v pokrytí)
- [x] Souhrn a doporučené pořadí

---

## 1 · honbicka/llm.py

### Mechanismus
- 🔴 **L1 · Jednotné volání „JSON + pydantic" v klientu.** `generuj_json` opakuje jen při
  nevalidním *JSONu*; pydantic validace probíhá až na volajících místech a každé ji řeší
  jinak (architekt vrací error-tuple, vypravěč má vlastní retry, koncept/téma dřív padaly).
  Oba živé pády generace („čtyři světla" #1, téma-generátor) by nevznikly, kdyby existovalo
  `generuj_model(role, prompt, Model) -> Model`, které v JEDNÉ retry smyčce řeší
  json.loads + `Model.model_validate` + opravný prompt s výpisem pydantic chyb.
  Volající místa by se zjednodušila a chování sjednotilo.
  **✅ OPRAVENO 2026-07-05.** `OllamaKlient.generuj_model(role, uzivatel, model_cls,
  schema=None, extra_system=None) -> ModelT` přidán do `honbicka/llm.py` — jedna
  `MAX_RETRY`-smyčka: `json.loads` selže → opravný prompt s chybou parseru;
  `model_cls.model_validate` selže → opravný prompt s `ValidationError`
  (počet chyb + detail). Testováno v `tests/test_llm.py`
  (`test_generuj_model_uspech`, `_retry_po_nevalidnim_json`,
  `_retry_po_pydantic_chybe`, `_tvrdy_fail_po_vycerpani`).
  **Zapojeno jen do `vygeneruj_tema`** — NE do `faze1a_koncept`, architekta ani
  vypravěče. Důvod (viz `docs/rozhodnuti.md`): tyto tři mají vlastní
  role-specifickou opravnou logiku (mechanická normalizace, game-validity
  feedback přes relosování, O1 fit-check), která se do jedné generické
  JSON+pydantic smyčky nedá bezeztrátově sbalit — a `vygeneruj_tema` navíc
  narazilo na jinou past: `Zadani.vek` je povinné pole, které model nespolehlivě
  vrací, ale plán ho musí přepsat PŘED validací (ne po ní) — `generuj_model`
  validuje hned, takže chybějící `vek` by zbytečně spotřeboval retries a nakonec
  spadl, i když má triviální opravu. `vygeneruj_tema` tedy zůstává na
  `generuj_json` + ruční patch dictu před `Zadani.model_validate`; normalizace
  diakritiky u `obtiznost` se ale přesunula z volající funkce do
  `field_validator(mode="before")` na `Zadani` samotném (čistší, funguje i pro
  budoucí volající místa). `generuj_model` je tak zatím jen jeden hotový,
  otestovaný call site + reusable primitive pro příště.
- 🔴 **L2 · Per-model `think` handling.** Ollama vrací HTTP 400 pro `think:true` na
  ne-thinking modelu (ověřeno sondou qwen3-coder). Klient s `model=` overridem se rozbije.
  Návrh: parametr `OllamaKlient(thinking_podporovano=True)` nebo detekce přes
  `/api/show` při prvním volání; při 400 s "think" jednorázově zopakovat bez něj.
  **✅ OPRAVENO 2026-07-05.** `_http_transport` rozliší HTTP 400 s `think:true`
  v payloadu a vyhodí `_ThinkingNotSupported`. `OllamaKlient._volej` na ni
  zareaguje jedním pokusem bez thinking (`think=False`); pokud role už
  `thinking=False` měla, nebo selže i podruhé → `HonbickaLLMError` (nekonečná
  smyčka vyloučena, max 2 pokusy). Žádná detekce přes `/api/show` předem —
  jednodušší je reagovat až na skutečné 400, ne modelovat schopnosti dopředu.
  Testy: `test_volej_zkusi_bez_thinking_kdyz_model_odmitne`,
  `_bez_thinking_odmitnuti_je_tvrdy_fail`, `_odmitnuti_i_bez_thinking_je_tvrdy_fail`,
  `test_http_transport_400_s_think_je_thinking_not_supported`,
  `_400_bez_think_neni_zvlastni_chyba` (obyčejné 400 beze změny chování).
- 🟡 **L3 · Retry na transientní chyby transportu.** ReadTimeout/5xx = okamžitý tvrdý fail.
  Redaktor tak ztratil 7/7 posudků. Návrh: 1 opakování na timeout/5xx (s logem), teprve
  pak `HonbickaLLMError`. (Spec §1 předepisuje 3× retry jen pro nevalidní JSON — retry na
  síťovou chybu je doplněk, ne obcházení.)
  **✅ OPRAVENO 2026-07-05.** `_http_transport` mapuje 5xx a
  `Timeout`/`ConnectionError` na `_PrechodnaChyba`; `OllamaKlient._volej_pokus`
  na ni zkusí 1× zopakovat (bez logu — TODO, viz níže), pak tvrdý fail.
  Testy: `test_volej_opakuje_na_prechodnou_chybu`,
  `_prechodna_chyba_dvakrat_je_tvrdy_fail`, `test_http_transport_5xx_je_prechodna_chyba`,
  `_timeout_je_prechodna_chyba`. **Log při opakování NEimplementován** — zůstává
  drobný dluh pro pozorovatelnost (spec nevyžaduje, jen doporučeno v návrhu).
- 🟡 **L4 · `_base_url` pašované v payloadu.** `payload["_base_url"]` + `pop()` v transportu
  je křehké (mock transporty klíč vidí a musí ho ignorovat). Čistší: `Transport =
  Callable[[str, dict, float], dict]` (base_url jako argument).
- 🟡 **L5 · `keep_alive`.** Ollama defaultně uvolní model po ~5 min nečinnosti. Mezi hrami
  v dávce (zápis, validace, sazba) může dojít k unload→reload (~30 s ztráta). Přidat
  `"keep_alive": "30m"` do payloadu.
  **✅ OPRAVENO 2026-07-05.** `OllamaKlient(keep_alive="30m")` (nový parametr
  konstruktoru, `DEFAULT_KEEP_ALIVE = "30m"`) — jde do payloadu u každého
  volání (`_volej_pokus`). Přepsatelné per-klient (`keep_alive="5m"` apod.),
  žádná role-specifická logika navíc. Testy `test_keep_alive_v_payloadu_ma_vychozi_hodnotu`,
  `_lze_prepsat`.
- 🟢 **L6 · `generuj_text` je mrtvý kód** — nikde se nevolá (vypravěč používá structured
  output). Smazat, nebo označit jako záměrné API do budoucna.

### Rychlost
- 🔴 **L7 · Redaktor: 7 sekvenčních thinking-ON volání = hlavní časový zabiják**
  (~15 min timeoutů v živém běhu). Návrhy v pořadí účinnosti:
  (a) jedno volání se schématem `list[RedakceVerdikt]` pro všech 7 checků najednou
  (7× méně prefill+thinking), fallback per-check při selhání;
  (b) thinking OFF pro redaktora (temp 0.3 zůstává) — thinking je u klasifikační úlohy
  s citacemi pravděpodobně zbytný; ověřit živě;
  (c) menší `num_ctx` (viz L8).
  **✅ OPRAVENO 2026-07-04 (varianta a).** `faze4_redaktor` nově volá LLM
  JEDNOU se schématem `RedakceVsechnyVerdikty` (pole `verdikty`, 7 položek).
  Selže-li (timeout/schema chyba/cokoliv) → `_faze4_redaktor_po_jednom`
  (stará logika, teď záložní cesta). Chybějící checky v odpovědi (model
  nevrátil přesně 7) se doplní jako FAILED, ne že by se tiše ztratily.
  **(b) thinking OFF NEvyzkoušeno** — jedno volání už řeší hlavní příčinu
  (počet volání, ne thinking samotné); vypínat thinking bez živého ověření
  je zbytečné riziko. **(c) menší `num_ctx` NEudělalo** — viz L8 níže.
- 🟡 **L8 · `num_ctx` 32768 pro redaktora je předimenzované** — vstup je ~4000 znaků
  (≈1500 tokenů). 8192–16384 stačí a šetří VRAM/prefill. U architekta je 32768 oprávněné
  jen pro legacy cestu s přiloženou předchozí mapou; scaffolder architekta nevolá.
- 🟢 **L9 · Streaming (`stream:true`)** — dnes timeout zahodí i téměř hotovou odpověď.
  Se streamem lze resetovat timeout per-token („idle timeout" místo „total timeout")
  a dlouhé generace přestanou umírat na pevný strop.

### Správnost popisů
- 🟡 **L10 · Docstringy lžou o počtu rolí:** modul říká „tři pracovní role + téma-generátor",
  třída `OllamaKlient` „k jednomu modelu se třemi rolemi" — enum má ČTYŘI role a klient
  slouží všem. Sjednotit na „čtyři role".
- 🟡 **L11 · `generuj_text` docstring** („pro role, jejichž výstupem jsou volné texty
  karet") popisuje něco, co se neděje — texty karet jdou přes structured output.
- 🟢 **L12 · `RoleConfig` docstring** odkazuje na „doplní M3/M4/M7" — milníky hotové,
  odkaz je zastaralý.

---

## 2 · honbicka/orchestrator.py

### Mechanismus
- 🔴 **O1 · Volby v textu karty se neověřují proti grafu.** Živý běh „čtyři světla"
  ukázal, že vypravěč si čísla voleb vymýšlí (karta 8 měla „→8" — odkaz sama na sebe;
  graf vede 8→10/11). Vytištěná hra by hráče posílala na špatné karty — **chyba
  správnosti finálního produktu**. Návrh (deterministicky, dle „Python rozhoduje"):
  po vygenerování karty vytáhnout regexem `→(\d+)` z `predni`/`zadni`, porovnat
  s `{h.cil for h in uzel.hrany}`; při neshodě cílený opravný pokus („volby vedou
  PŘESNĚ na čísla: …"); prompt vypravěče má cílová čísla vyjmenovat jako povinná.
  **✅ OPRAVENO 2026-07-04:** `_volby_v_karte_platne()` + `_ocekavana_cisla_voleb()`
  (`honbicka/orchestrator.py`) ověří `predni`/`zadni`/`zadni_30` proti hranám uzlu
  (zadni_30 proti CORE podmnožině). `napis_kartu` při neshodě zopakuje s cíleným
  opravným promptem (nová „KRITICKÉ: čísla za šipkou…" věta v base promptu +
  `oprava_voleb` korekce); po vyčerpání pokusů `_oprav_volby_deterministicky()`
  jednoznačně přepíše všechna „→N" na jediný platný cíl (má-li uzel jen 1 hranu);
  víc hran = nejednoznačné, zaloguje se `volby_neopravitelne` a probublá do
  `report.chyby`. Ověřeno retroaktivně na živých datech (karta 8 „čtyři světla":
  `_volby_v_karte_platne` správně vrátí False). 14 nových testů
  (`tests/test_vypravec_volby.py`), 173/173 (bez slow), ruff čistý.
- 🔴 **O2 · Redaktor vidí jen zlomek hry.** `blob[:4000]` = ~4 karty z 21, navíc slepé
  oříznutí uprostřed karty a bias na nízká čísla. R4 („namátkou 5 karet") ani R1
  (průnik stop) nelze poctivě posoudit. Návrh: místo prefixu **vzorkovat celé karty**
  (AHA karta + klíčové svědectví + 3–4 náhodné dle seedu) a pro R1/R2 přidat
  koncept (mechanismus řešení) do promptu.
  **✅ OPRAVENO 2026-07-04:** `_vzorkuj_karty_pro_redakci()` — AHA karta +
  všechny karty s `klicove_svedectvi` + 4 náhodné (seed = `mapa.seed`,
  deterministické), CELÝ obsah karet (žádné oříznutí uprostřed). Prompt
  jednoho sloučeného volání (viz L7) navíc posílá `koncept.mechanismus_reseni`
  jako kontext pro R1/R2. Bez `mapa` (staré/testovací volání) se použijí
  všechny karty beze změny.
- 🔴 **O3 · Vypravěč nezná zápletku.** Prompt karty předává jen téma+typ+sousedy —
  ne mechanismus řešení, falešné teorie, rekvizitu. Každá karta si proto vymýšlí
  vlastní příběhové prvky (v „čtyřech světlech" viditelné: karty jsou atmosférické,
  ale narativně nespojité — zrcadla, panely, lampy bez souvislosti). Návrh: do
  promptu přidat 2–3 řádky konceptu (mechanismus, rekvizita, falešná teorie) +
  instrukci, co karta smí/nesmí prozradit vzhledem k pozici před/za AHA.
  **Pravděpodobně největší páka na kvalitu obsahu.**
  **✅ OPRAVENO 2026-07-04:** `_prompt_vypravec` teď posílá „SKRYTÉ POZADÍ
  PŘÍBĚHU" (mechanismus řešení + klíčová rekvizita) s explicitním „NIKDY
  neprozraď přímo" (P0 „pravda se odvozuje"). `_kontext_karty` doplňuje
  heuristiku `pred_aha` (číslo uzlu < AHA uzel ≈ karta je dřív v trunku —
  orientační, ne grafově přesné kvůli větvím/SIDE) → karta dostane „PŘED
  odhalením" (smí jen naznačovat) nebo „PO odhalení" (smí navazovat) instrukci;
  samotná AHA karta má svou vlastní (nezměněnou) instrukci. 3 nové testy
  (mechanismus+rekvizita v promptu, před/po rozlišení, AHA karta nemá
  před/po text), 191/191 (bez slow), ruff čistý. **Zbývá ověřit živě** (na
  reálném modelu), jestli to skutečně zlepší narativní soudržnost karet —
  mimo dosah tohoto prostředí bez spuštění dalšího dlouhého živého běhu.
- 🔴 **O4 · Slovník žánru (Patro 1 bod 10) neimplementován.** `Koncept.slovnik_zakazana`
  existuje, ale žádná kontrola karty negrepuje. Deterministická kontrola je triviální
  (substring přes všechny strany karet) — přidat do FÁZE 3 hned za fit-check
  (s cíleným opravným promptem „nahraď slovo X").
- 🟡 **O5 · Koncept je hubený a kazí okna zákazů.** Živě: `mechanismus_reseni=
  "prunik_stop"`, rekvizita `"denik_detektiva"` (snake_case tokeny). Tyto řetězce se
  zapisují do registru a porovnávají v oknech zákazů — generické tokeny učiní
  deduplikaci bezcennou (každá hra „prunik_stop" = kolize navždy). Návrh: prompt
  konceptu s příkladem plných vět („Drak kýchá kvůli pylu květiny — hráč to odvodí
  z…"), min. délka pole validovaná pydantic (`min_length`).
  **✅ OPRAVENO 2026-07-04:** `Koncept.mechanismus_reseni` má `min_length=15` +
  `field_validator` odmítající snake_case (musí obsahovat mezeru, ne podtržítko);
  `klicova_rekvizita` odmítá podtržítko (smí být i jedno slovo — rekvizita
  není celá věta). `faze1a_koncept` má nový příklad DOBŘE/ŠPATNĚ v base
  promptu + opravnou smyčku (`MAX_ITERACI_KONCEPT=3`, cílený re-prompt s
  počtem chyb) + mechanickou poslední záchranu (`_normalizuj_koncept_data`:
  podtržítka→mezery, prázdné/krátké doplní obecnou frází) — hra nikdy nespadne
  jen na kosmetickém poli. 8 nových testů (příklad v promptu, retry po
  snake_case, mechanická oprava po vyčerpání, normalizace prázdného/rekvizity,
  validátor odmítá krátký i dost dlouhý snake_case). **Zbývá:** pokud po
  mechanické opravě selže i JINÉ pole (schéma jinak vadné), `faze1a_koncept`
  vyhodí `RuntimeError` nezachycený ve `vyrob_hru` — sjednotí až L1 (úkol 9).
- 🟡 **O6 · Nouzová karta nemá volby.** `_nouzova_karta` negeneruje „→ karta X" —
  vytištěná by rozbila navigaci. Doplnit hrany uzlu jako generické volby
  („A) Pokračuj → karta {cil}").
  **✅ OPRAVENO 2026-07-04:** `_nouzove_volby()` vygeneruje „A) Pokračuj → N"
  pro každou hranu uzlu (přímo z grafu, ne z LLM — nikdy neselže O1 kontrolu).
  `_nouzova_karta` teď bere i `mapa` a doplní `zadni_30` (jen CORE cíle) pro
  CORE rozcestníky se SIDE sousedem. Cílová karta (bez hran) dostane text
  „Příběh na této kartě končí." bez falešných šipek. 7 nových testů
  (1 hrana, více hran, cílová karta, zadni_30, end-to-end přes `napis_kartu`
  po vyčerpání schema-pokusů), 188/188 (bez slow), ruff čistý.
- 🟡 **O7 · Kolize slugu.** Slug se odvozuje z tématu; opakovaná hra se stejným
  tématem přepíše `skiny/<slug>/` a registr dostane duplicitní slug. Návrh: při
  existenci adresáře přidat sufix `-{seed}`.
- 🟡 **O8 · Trojí validace téže mapy.** Scaffolder interně simuluje (výběr AHA),
  `vyrob_hru` validuje s `POCET_SIMULACI=15`, a pak `validuj_par_30_60` běží PO TŘETÍ
  (default 5) jen kvůli `sim_reports` — výsledky první validace se zahazují (`_`).
  Návrh: použít reporty z první validace (funkce je už vrací) a smazat třetí běh.
  Zároveň sjednotit počet průchodů (15 vs 5 dává jiný medián — zdroj dřívějšího bugu).
  **✅ OPRAVENO 2026-07-05.** `vyrob_hru` teď drží `sim_mapa_faze1` z validace
  ve FÁZI 1b (scaffolder cesta) a znovu ji použije jako `sim_reports` v
  závěrečném reportu — místo TŘETÍHO běhu `validuj_par_30_60` nad stejnou
  mapou. Bezpečné, protože simulace je deterministická (seed = `mapa.seed`)
  a graf se po FÁZI 1 nemění (FÁZE 3/SC3 mění jen `Uzel.nazev`, ne
  hrany/podmínky). Legacy architekt cesta (`pouzij_scaffolder=False`) svou
  validaci ve FÁZI 1b nevrací ven, takže tam zůstává jeden dopočet na konci
  (`sim_mapa_faze1 is None` → fallback) — beze změny oproti dřívějšímu chování,
  jen teď se jmenovaným defaultem. Scaffolderovo VLASTNÍ interní simulování
  (výběr AHA uzlu v `_vyber_aha_uzel`) je samostatný účel (hledá NEJLEPŠÍ
  pozici AHA, ne ověřuje HOTOVOU mapu) a nedá se s touhle validací sloučit —
  zůstává tak, jak bylo. Test `test_vyrob_hru_scaffolder_validuje_mapu_jen_jednou`
  (počítá volání `validuj_par_30_60` přes monkeypatch wrapper, ověřuje `n==1`).
- 🟡 **O9 · `_pdf_sady` chytá jen `SazbaNedostupna`.** Jiná výjimka WeasyPrintu
  (chyba fontu, interní chyba na konkrétní kartě) shodí celou hru PO drahé generaci.
  Chytat `Exception` → zapsat do `report.chyby` (skin už je uložený, měkký fail).
  **✅ OPRAVENO 2026-07-05.** `_pdf_sady` teď vrací `(ok, chyba)` místo holého
  `bool`; přidán `except Exception as exc` po `SazbaNedostupna` (`# noqa: BLE001`,
  vědomě široký — je to poslední záchranná síť PO uloženém skinu), zpráva jde
  do `report.chyby` jako `f"PDF nevyrenderováno ({pdf_chyba or 'GTK/WeasyPrint chybí'})"`
  — takže SazbaNedostupna dál hlásí obecné „GTK/WeasyPrint chybí", ale
  neočekávaná chyba (font, render pádu) teď nese vlastní `TypChyby: zpráva`.
  Test `test_vyrob_hru_pdf_jina_vyjimka_nez_sazbanedostupna_je_mekky_fail`
  (monkeypatch `uloz_pdf_karet` → `RuntimeError`) ověřuje `hra.report.stav ==
  OK` i čitelnou zprávu.
- 🟡 **O10 · `ATMOSFERA_FLOOR=200` porušuje dodatek 3.4-7** (atmosféra 300–500 znaků
  POVINNÁ). Ořez smí jít pod 300. Rozhodnout: buď floor 300 + při nevejití nechat
  fit-check fail (a řešit zkrácením mechaniky?… ne — spíš re-prompt), nebo odchylku
  explicitně zapsat do docs/rozhodnuti.md. Teď je to tichý rozpor.
- 🟢 **O11 · `LosovaneParametry.pocet_karet_60` scaffolder ignoruje** (staví fix 21),
  ale losování ho dál generuje a loguje — matoucí stopa v logu. Buď z losování pro
  scaffolder cestu vyřadit, nebo zalogovat „scaffolder: pevných 21".
- 🟢 **O12 · Spec-mezery (vědomé, k evidenci):** Patro 1 bod 11 (bezpečnost úkolů dle
  physical_intensity/prostředí — banka úkolů nemodelována), bod 13 (bypass), P9/kostkové
  tabulky 1–6 jako strukturovaná data. Zapsáno i v rozhodnuti.md; sem pro úplnost.

### Rychlost
- 🔴 **O13 · FÁZE 4 = 7 × thinking-ON volání** (viz L7) — v živém běhu ~15 min
  timeoutů, 0 užitku. Jedno volání s `list[RedakceVerdikt]` + vzorkované karty (O2)
  srazí redakci na ~1–2 min.
  **✅ OPRAVENO 2026-07-04** — viz L7 (implementace) a O2 (vzorkování). 9
  nových testů (jedno volání stačí, chybějící check se doplní, fallback po
  jednom, vzorkování AHA/klíč. svědectví/determinismus/řazení), 206/206
  (bez slow), ruff čistý. **Živé ověření skutečné časové úspory
  neprovedeno** — vyžadovalo by další dlouhý živý běh; teoreticky 7×
  méně prefillu+thinking, ale reálný dopad na wall-clock čas nebyl změřen.
- 🟡 **O14 · Duplicitní simulace/validace** (O8) — malé, ale zbytečné.
- 🟢 **O15 · Vypravěč `num_ctx` 16384** při ~1,5k tokenech promptu — 8192 stačí,
  rychlejší prefill a méně VRAM (víc místa pro KV cache jiných volání).

### Správnost popisů
- 🔴 **O16 · Docstring modulu je zastaralý:** „M3 implementuje FÁZE 0 a FÁZE 1 …
  FÁZE 3–5 doplní M4–M6" — vše je hotové a default cesta jde přes scaffolder, který
  v docstringu chybí. Přepsat na skutečný tok (FÁZE 1 = koncept LLM + scaffolder;
  legacy LLM architekt za flagem).
- 🟡 **O17 · Sekce „FÁZE 1 — ARCHITEKT (koncept + mapa)"** — mapa už defaultně
  nevzniká u architekta; nadpis sekce a docstring `faze1_architekt` označit „legacy".
- 🟢 **O18 · Překlep** v komentáři: „balíček nešhodí" (ř. 697) → „neshodí".
- 🟢 **O19 · `_normalizuj_kartu`** docstring říká „doplní typ/nazev" — doplňuje i
  `cislo` z `id`; drobně rozšířit.

---

## 3 · honbicka/modely.py

### Mechanismus
- 🟡 **MD1 · `Hrana.fyzicka_narocnost: str`** — volný string; má být
  `Literal["low", "high"]` (pydantic pak odmítne překlepy). Souvisí s neimplementovaným
  dodatkem 3.4-6 (viz V6 níže), který na tomto poli stojí.
- 🟡 **MD2 · `Pravdivost` enum je mrtvý.** Uzel typu INFORMACE nemá pravdivostní
  hodnotu (pravda/zavadejici/lez) — proto minima pravdivých stop (§SKÁLOVÁNÍ) nelze
  strojově ověřit z mapy (je to jen číslo v konceptu) a R1/R2 nemají datovou oporu.
  Návrh: `Uzel.pravdivost: Pravdivost | None`, scaffolder rozdělí pravda/lež dle
  koncept-počtů, `skalovani` pak počítá skutečné stopy.
- 🟡 **MD3 · `Karta.atmosfera` bez min. délky.** Popis říká „300–500 znaků povinný",
  ale nic to nevynucuje (a ořez smí jít na 200 — viz O10). Přidat validaci nebo
  aspoň deterministickou kontrolu ve FÁZE 3 s re-promptem.
- 🟢 **MD4 · `Hra.koncept: str` (markdown)** vedle typované `mapa: Mapa` — asymetrie;
  strukturovaný `Koncept` se ztrácí (je jen v .md). Uložit i objekt (koncept.json).

### Správnost popisů
- 🟢 **MD5 ·** Popisy polí OK (po dřívějších opravách). `SCHEMA_*` konstanty
  odpovídají realitě.

---

## 4 · honbicka/scaffold.py

### Mechanismus
- 🔴 **SC1 · Chybí POSTAVY dle engine tabulky.** §SKÁLOVÁNÍ: postavy 60min = **5–7**,
  30min = **3–4**. Skeleton má **1** uzel typu `postava` (a validátor to nekontroluje
  — viz V1, proto 3600/3600 prošlo). Navíc **chybí `lecitel`** (engine: stavy „vždy
  léčitelné" — herní list na léčitele odkazuje, ale v mapě není!) a **postava
  nápovědy** (§SYSTÉM NÁPOVĚDY: 1–2 v mapě; práh počítadla bez ní nemá payoff).
  Návrh: přetypovat část prechod/informace uzlů na `postava`, přidat `lecitel`
  do CORE a označit postavu nápovědy. **Největší věcný dluh scaffolderu vůči enginu.**
  **✅ OPRAVENO 2026-07-04:** uzly 7 a 10 (CORE) přetypovány na `postava`
  (edge-count „větve" kontrola je na typu nezávislá, takže retyp je bezpečný);
  uzel 13 (SIDE) na `lecitel`, uzel 14 (SIDE) na `postava`. CORE má nyní 3
  postavy (7,8,10 → 30min rozsah 3–4 ✓), plný 60min graf 4 postavy + 1 léčitel
  = 5 (rozsah 5–7 ✓). „Postava nápovědy" nemá vlastní typ v modelu (engine ji
  neodlišuje strukturně) — dostatek `postava` uzlů stačí, aby ji vypravěč mohl
  narativně přiřadit jedné z nich; neimplementováno jako samostatné pole.
- 🟡 **SC2 · Jediný topologický vzor.** Zapsáno v rozhodnuti.md jako kompromis;
  s parametrem `rng` (dnes nevyužitý!) lze levně variovat: prohodit pořadí větví,
  posunout gated/strez pozice, střídat 2–3 předpřipravené vzory trunku. Bez toho
  budou všechny hry strukturálně identické (hráči vzor prokouknou — přesně proti
  §RITUÁL vs. PŘEKVAPENÍ).
- 🟡 **SC3 · Generické názvy uzlů prosáknou do průvodce.** Uzly se jmenují
  „prechod 10", „jednosmer 21" — a průvodce (Rozmístění uzlů!) je tiskne organizátorovi.
  Vypravěč mezitím vymyslí vlastní názvy karet → mapa a karty se rozjedou (živě
  ověřeno: karta „Čtyři světla" 3×). Návrh: po FÁZE 3 zpětně propsat názvy karet
  do `mapa.uzly[].nazev` (deterministická synchronizace) + vypravěči přikázat
  unikátní název.
  **✅ OPRAVENO 2026-07-05.** `_synchronizuj_nazvy_uzlu(mapa, karty)` v
  `honbicka/orchestrator.py` — po vygenerování všech karet (na konci
  `faze3_vypravec`, PŘED `_zapis_skin`/sazbou) projde karty dle čísla uzlu a
  přepíše `mapa.uzel(karta.cislo).nazev = karta.nazev`. Žádné nové LLM volání
  (deterministické, spec §3 „Python rozhoduje"). Duplicitní jména (dva uzly se
  stejným nápadem vypravěče) se rozliší suffixem `" (<číslo uzlu>)"`, aby
  signage na uzlech zůstalo jednoznačné. `pruvodce.py` (řádek 76, „Rozmístění
  uzlů") i karty (řádek 117) tak po opravě tisknou STEJNÝ název pro stejné
  číslo. **Vypravěči NEbyla přidána instrukce „unikátní název"** — dedupe řeší
  Python deterministicky po faktu, což je spolehlivější než spoléhat na model;
  promptová instrukce by byla jen kosmetická nadstavba bez záruky. 4 nové testy
  v `tests/test_vypravec.py` (`_synchronizuj_nazvy_uzlu` přepis/dedupe/obranné
  chování + integrace přes `faze3_vypravec`), 223/223 (bez slow), ruff čistý.
- 🟢 **SC4 · `rng` parametr nevyužit** — buď použít (SC2), nebo z podpisu vyřadit.

### Správnost popisů
- 🟢 **SC5 ·** Docstring přesný (i adaptivní AHA). Jen doplnit poznámku o SC1 limitu,
  dokud se nevyřeší.

---

## 5 · honbicka/validatory/

### Mechanismus
- 🔴 **V1 · `skalovani` nekontroluje POSTAVY (řádek engine tabulky chybí).**
  `SkalaProfilu` nemá pole pro postavy (3–4 / 5–7) — proto prošel skeleton s 1 postavou.
  Přidat `postavy: tuple[int, int]` (počítat typy `postava`+`lecitel`; obchodník má
  vlastní řádek) a rozšířit tabulku. Totéž zvážit pro „Řetězec předmětů (P6)"
  (60min: 1× ≥3 články) — dnes zcela nekontrolováno a nemodelováno.
  **✅ OPRAVENO 2026-07-04:** `SkalaProfilu.postavy` (30min=(3,4), 60min=(5,7)),
  kontrola v `zkontroluj_skalovani` počítá `typ(POSTAVA)+typ(LECITEL)` (obchodník
  se do součtu nepočítá, viz vlastní `obchodnik_povinny` check). 4 nové testy
  (`test_skalovani.py`: málo postav, léčitel se počítá, moc postav, obchodník se
  nepočítá). **Řetězec předmětů (P6) zůstává nemodelován** — mimo rozsah tohoto
  fixu, ponecháno jako otevřená položka.
  **Vedlejší nález (NEOPRAVENO, mimo rozsah SC1/V1):** při plné 3600-kombinační
  validaci scaffolderu (viz SC1) se objevilo **180/3600 (5 %) předem existujících
  selhání** — archetyp A1, konkrétní seedy (např. seed=3) → pozice AHA padne na
  82–88 % místo do pásma 65–80/87 %. **Ověřeno diffem se starým scaffolderem
  (`git stash`): identická množina selhání před i po SC1/V1 změnách** — nejde
  o regresi, je to dřívější neobjevený okrajový případ v `_vyber_aha_uzel`
  (pravděpodobně: candidate-uzly mezi sebou nemají dost jemné rozestupy % pro
  úzké pásmo A1 při určitých seedech). `vyrob_hru` toto zachytí jako FAILED
  hru (bezpečné selhání, netiskne se nic špatného), ale podkopává slib
  scaffolderu „vždy uspěje deterministicky". **Kandidát na další opravu**
  (mimo aktuální dávku): buď rozšířit sadu kandidátních uzlů (víc dominátorů
  v trunku), nebo při vyčerpání kandidátů zkusit posunout AHA_UZEL_DEFAULT
  jinam / lehce poupravit tempo uzlů před AHA.
- 🟡 **V2 · Simulace ignoruje `Hrana.podminka` a inventář.** Spec Patro 1 bod 12 chce
  průchody „s inventářem, komponentami, stavy". BFS agent bere gated hranu jako volnou.
  Dnes neškodí (scaffolder podmínky na hrany nedává), ale jakmile je dá, délka i AHA %
  budou podhodnocené. Návrh: agent sbírá komponenty při návštěvě uzlu a hranu
  s podmínkou smí projít až po jejím splnění.
- 🟡 **V3 · Totéž v `topologie`:** dosažitelnost/softlock počítá podmíněné hrany jako
  průchozí — „dosažitelný" uzel může být za nesplnitelnou podmínkou. Minimálně
  zdokumentovat; correctness fix = dosažitelnost po vrstvách (bez podmínek → s
  postupně splnitelnými podmínkami).
- 🟡 **V4 · Nejednotný `pocet_simulaci`** napříč voláními (5 default vs 15 scaffolder)
  — už způsobil bug (medián se lišil). Návrh: jediná konstanta v `validatory.simulace`
  (např. `POCET_SIMULACI_DEFAULT = 15`), všude importovat; `scaffold.POCET_SIMULACI`
  z ní jen aliasovat.
  **✅ OPRAVENO 2026-07-05.** `POCET_SIMULACI_DEFAULT = 15` přidán do
  `honbicka/validatory/simulace.py` — jediný zdroj. `simuluj()`,
  `validuj_mapu()`, `validuj_par_30_60()` (agregace.py) na něj teď defaultují
  místo hardcoded `5`; `scaffold.POCET_SIMULACI` je čistý alias
  (`POCET_SIMULACI = POCET_SIMULACI_DEFAULT`). Test
  `test_pocet_simulaci_je_sjednoceny_s_validatorem` v `test_scaffold.py`.
- 🟡 **V5 · `sazba._weasy_measurer` používá privátní API** `page._page_box.children[0]`
  — křehké napříč verzemi WeasyPrintu (CI má 69.0, pin v pyproject je jen `>=61`).
  Návrh: pin horní meze verze, nebo měřit přes veřejné API (render do
  jednostránkového dokumentu a číst `page.height` obsahového boxu přes descendants).
- 🔴 **V6 · Dodatek 3.4-6 (přístupnost) neimplementován.** „K postavám s klíčovým
  svědectvím vždy ≥1 fyzicky nenáročná hrana" — pole `fyzicka_narocnost` existuje,
  kontrola nikde. Deterministická a triviální: pro každý uzel s
  `klicove_svedectvi=true` ověřit ≥1 vstupní hranu s `fyzicka_narocnost=="low"`.
- 🟢 **V7 · `zkontroluj_simulaci` míchá zodpovědnosti** (délka z `odhad_delky_min`,
  AHA z průchodů, dominátory) — funguje, ale rozpadnout na tři pojmenované kontroly
  by zlepšilo diagnostiky.

### Rychlost
- 🟢 **V8 · `povinne_uzly` je O(N·(N+E))** (BFS bez každého uzlu) — pro 21 uzlů
  irelevantní; kdyby mapy narostly (90min, 35 uzlů), pořád OK. Nic nedělat.

### Správnost popisů
- 🟡 **V9 · `topologie._minima_pro` docstring** neříká, že minima „větví" počítá jako
  uzly s ≥2 hranami (tj. včetně střežených apod.), zatímco engine mluví o „≥3 větve"
  topologicky. Upřesnit definici v docstringu.
- 🟢 **V10 · `simulace` docstring** slibuje „edge-case scénáře" (chybějící předmět,
  pokus o falešné řešení, počítadlo pod/nad prahem — spec §VALIDACE Simulace) —
  neimplementováno. Buď doplnit, nebo z docstringu odstranit a zapsat jako spec-mezeru.

---

## 6 · honbicka/sazba/

### Mechanismus / správnost tisku
- 🔴 **SZ1 · Duplex instrukce je pro landscape arch pravděpodobně ŠPATNĚ.**
  Klasická tiskařská past: portrait dokumenty = „otáčet po delší straně", **landscape
  dokumenty typicky „po kratší straně"** (jinak zadní strany vzhůru nohama). Náš arch
  je A4 na šířku; průvodce i kalibrační karta instruují „po delší straně" a imposice
  drží levý slot vlevo — což sedí jen pro jeden režim otočení: při otočení po kratší
  straně se sloty zrcadlí L↔R (zadní arch by musel mít pořadí B|A). Nelze rozhodnout
  od stolu — **závisí na ovladači tiskárny**. Návrh: (a) kalibrační značky udělat
  ASYMETRICKÉ (písmeno/šipka v rohu — dnes je to symetrický čtverec, který neodhalí
  otočení o 180° ani zrcadlení spolehlivě), (b) do průvodce dát OBĚ varianty
  („pokud je zadní strana vzhůru nohama, přepni na kratší stranu"), (c) volitelně
  generovat obě zadní imposice. Ověřit prvním reálným tiskem.
  **✅ ČÁSTEČNĚ OPRAVENO 2026-07-04** (a)+(b) implementovány, (c) vědomě
  vynechánO — viz níže. `_kalibrace()` (`honbicka/sazba/karty_pdf.py`): symetrický
  čtverec uprostřed nahrazen CSS trojúhelníkem („SMĚR →" + popisek „HORNÍ ROH")
  posunutým MIMO střed i osy souměrnosti slotu (15mm/15mm místo ~74mm/105mm) —
  taková značka spolehlivě odhalí i zrcadlené otočení (symetrický středový čtverec
  by se pod špatnou transformací mohl náhodně stále překrývat). Kalibrace i
  průvodce (`pruvodce.py`) teď explicitně nabízí OBĚ varianty („delší" i „kratší
  strana") s návodem, co dělat, když se značky nekryjí/šipka míří jinam. **(c)
  vynecháno záměrně:** generování dvou zadních imposic by zdvojnásobilo PDF a
  zesložitilo tiskový postup; (a)+(b) dávají uživateli dost informace k
  samodiagnóze bez nutnosti dvou variant souboru. Reálný tisk (fyzická
  kalibrace) je mimo dosah tohoto prostředí — **vyžaduje ruční ověření
  uživatelem**. 3 nové testy (pozice mimo střed, asymetrický tvar, obě varianty
  v textu), 175/175 (bez slow), ruff čistý, reálný PDF render ověřen (6 stran).
- 🟡 **SZ2 · Měřicí stránka 4000 mm** v `_weasy_measurer` — obsah delší než 4000 mm
  by se stránkoval a výška lhala. U karet nehrozí, ale guard (assert 1 stránka) je
  zadarmo.
- 🟡 **SZ3 · `spocti_archy` počítá substring `class='arch'`** — svázané s přesnou
  syntaxí generátoru (jednoduché uvozovky). Křehké při refaktoru CSS/HTML; robustnější
  je počítat přes významový marker (např. `<!--arch-->` komentář) nebo parsovat.
- 🟢 **SZ4 · Herní list nemá kostkové tabulky 1–6** (§KOSTKA: na sber/prechod uzlech
  tabulka šesti mikroúkolů) ani zápis „banka úkolů dle prostředí" — súvisí s O12/V10
  spec-mezerami; evidovat.

### Správnost popisů
- 🟢 **SZ5 · `styl.py`:** komentář „Pasti WeasyPrint jako CSS konstanty" přesný;
  `SYM_*` duplikované v `sazba/__init__.py` i `styl.py` — jeden zdroj pravdy.

---

## 7 · honbicka/registr.py + taxonomie.py

- 🟡 **R1 · Okna zákazů porovnávají přesné řetězce** (`mechanismus.lower()`), takže
  reálná ochrana proti opakování stojí na kvalitě koncept polí (viz O5 — dnes
  „prunik_stop" ⇒ všechna budoucí „prunik_stop" zakázána = fakticky blokace, nebo
  při jiném tokenu nulová ochrana). Po O5 zvážit fuzzy shodu (normalizace, klíčová
  slova) — jinak okna reálně nefungují.
  **ROZHODNUTO 2026-07-04 (NEimplementovat fuzzy shodu):** po opravě O5 nese
  `mechanismus_reseni` plnou větu (min. 15 znaků, ne token) → přesné porovnání
  je teď smysluplné (různé hry s odlišnou zápletkou mají odlišné věty; fuzzy
  shoda by hrozila falešně blokovat podobně znějící, ale reálně odlišné hry).
  Audit sám tuto položku formuloval jako „zvážit", ne požadavek — ponecháno
  jako budoucí vylepšení, ne bug.
- 🟡 **R2 · Kolize slugu v registru** (duplicitní řádky téhož slugu) — viz O7;
  registr je append-only, ale `nacti_registr` nijak neřeší duplicitní slug
  (pro okna zákazů to nevadí, pro `honbicka status` a lidské čtení ano).
- 🟢 **R3 · `zapis_zaznam`** připíše hlavičku jen když je soubor prázdný/neexistuje —
  soubor s obsahem bez hlavičky (ruční zásah) dostane řádky bez tabulky. Okrajové.
- 🟢 **R4 · `taxonomie.zatrid_hru`** — kopíruje jen PDF; bez GTK vznikne INDEX.md
  s „(PDF zatím nevygenerováno)" — správně. INDEX by mohl přiložit i herní listy
  ze `skiny/` (karty.json pro náhradu ztracené karty zmiňuje spec §7 příloha) — nice-to-have.

---

## 8 · honbicka/davka.py + feedback.py + cli.py

- 🔴 **C1 · `honbicka gen`/`batch` bez GTK spadne UPROSTŘED generace.** CLI nepředává
  `measurer` → default `_weasy_measurer` → první fit-check ve FÁZE 3 vyhodí
  `SazbaNedostupna` až PO zaplacení konceptu (+1 karty) na GPU. (Živé běhy to
  obcházely fake measurerem — CLI cesta je neotestovaná díra.) Návrh: na začátku
  `vyrob_hru` zavolat `sazba.render.je_dostupne()`; když ne → **fail-fast s jasnou
  hláškou PŘED prvním LLM voláním**, nebo explicitní `--bez-fitchecku` fallback na
  odhad znaků se zápisem „fit-check aproximován" do reportu (netisknout!).
  **✅ OPRAVENO 2026-07-04** (fail-fast varianta; fallback-na-odhad NEimplementován —
  viz níže). `vyrob_hru` po FÁZE 0 (levné, bez LLM/GTK) zkontroluje: pokud volající
  nepředal vlastní `measurer` A `je_dostupne()` je False → okamžitě vrátí
  `Hra`/`Report` se `stav=FAILED` a čitelnou chybou (zmiňuje `HONBICKA_GTK_DIR`),
  BEZ jediného volání `klient.generuj_json`. Vlastní `measurer` (testy, budoucí
  `--bez-fitchecku`) fail-fast obchází. `cli._cmd_gen` už chybu správně tiskl
  (`report.chyby`) — žádná změna v CLI nebyla potřeba. **Fallback „--bez-fitchecku"
  s odhadem znaků NEimplementován:** spec §12 „nikdy netiskneme naslepo" činí
  aproximovaný fit-check rizikovým i s varováním; fail-fast je bezpečnější
  výchozí chování. 4 nové testy (LLM nikdy nezavoláno, chyba obsahuje „GTK",
  vlastní measurer fail-fast obchází, CLI exit-kód 1 s hláškou), 183/183
  (bez slow), ruff čistý.
- 🟡 **C2 · Dávka nezapisuje průběžný report na disk.** `spust_davku` drží výsledky
  v paměti; pád/přerušení přes noc ztratí přehled (hry samotné na disku jsou).
  Návrh: append `skiny/davka_<timestamp>.jsonl` po každé hře.
- 🟡 **C3 · `spust_davku` čte feedbacky/registr každou hru** — správně (okna se
  aktualizují), jen zbytečně načítá feedbacky znovu; cache na úrovni dávky stačí.
- 🟢 **C4 · `honbicka new` netestované** (interaktivní input) — extrahovat čistou
  funkci `sestav_zadani(odpovedi) -> Zadani` a testovat tu; CLI zůstane tenké.
- 🟢 **C5 · `cli._cmd_gen` tiskne jen chyby** — přidat cestu ke skinu a součet
  fit-check/redakce (už je v reportu).

---

## 9 · tests/ — mezery v pokrytí

- 🔴 **T1 · Chybí test „volby v textu ↔ hrany grafu"** (O1) — nejdřív feature, pak test.
- 🟡 **T2 · Chybí test CLI `gen` cesty bez GTK** (C1) — dnes by odhalil pád.
- 🟡 **T3 · Chybí test počtů postav** (V1/SC1) — po doplnění tabulky přidat rozbitý graf
  s 1 postavou.
- 🟡 **T4 · `@slow` testy nepokrývají vypravěče ani redaktora** — právě ty dvě role
  živě selhaly. Přidat 1 slow test: `napis_kartu` na 1 uzlu (≤2 min) a 1 redaktor
  check. Levné a chytá regresi schémat.
- 🟢 **T5 · Golden PDF na CI:** CI má GTK — golden test může nově assertovat i reálný
  render (počet stran vyrenderovaného PDF přes pypdf), ne jen HTML archy. Zpřesní
  „Sazba: počet stran = f(počet karet)" ze spec §10.

---

## 10 · Souhrn — doporučené pořadí prací

**Vlna 1 — správnost tištěné hry (bez ní nemá smysl tisknout):**
1. ✅ O1+T1: volby v textu karet ↔ hrany grafu (deterministická kontrola + oprava promptu) — OPRAVENO 2026-07-04
2. ✅ SZ1: duplex/kalibrace — asymetrické značky + instrukce obou režimů — ČÁSTEČNĚ OPRAVENO 2026-07-04 (kód hotový; reálný tisk vyžaduje ruční ověření uživatelem)
3. ✅ SC1+V1+T3: postavy/léčitel/nápověda do scaffolderu + řádek tabulky do škálování — OPRAVENO 2026-07-04 (odhalen vedlejší nález: 180/3600 pre-existující AHA edge-case, netýká se této opravy, viz V1)
4. ✅ C1+T2: fail-fast bez GTK v CLI — OPRAVENO 2026-07-04
5. ✅ O6: nouzová karta s volbami — OPRAVENO 2026-07-04

**VLNA 1 DOKONČENA 2026-07-04** (body 1–5 výše). 188 testů (bez slow), ruff
čistý. Commity: viz git log (O1, SZ1, SC1+V1+T3, C1+T2, O6).

**Vlna 2 — kvalita obsahu a rychlost:**
6. ✅ O3: koncept do promptu vypravěče (narativní soudržnost) — OPRAVENO 2026-07-04 (živé ověření kvality zatím neprovedeno)
7. ✅ O5+R1: plnohodnotný koncept (věty, min_length) → funkční okna zákazů — OPRAVENO 2026-07-04 (R1 fuzzy shoda vědomě NEimplementována, viz sekce 7)
8. ✅ L7/O13: redaktor jedním voláním + vzorkované karty (O2) — OPRAVENO 2026-07-04 (thinking OFF test odloženo, živé měření času neprovedeno)
9. ✅ L1+L2+L3: `generuj_model` (JSON+pydantic v jedné retry smyčce) + per-model
   think fallback + retry na přechodnou transportní chybu — OPRAVENO 2026-07-05
   (`generuj_model` zapojen jen do `vygeneruj_tema`; architekt/vypravěč/koncept
   záměrně ponechány na vlastní logice — viz zdůvodnění u L1 výše)
10. ✅ SC3: synchronizace názvů uzlů ↔ karet (průvodce) — OPRAVENO 2026-07-05

**VLNA 2 DOKONČENA 2026-07-05** (body 6–10 výše). 223 testů (bez slow), ruff
čistý.

**Vlna 3 — robustnost a dluh:**
11. ~~L2 (per-model think), L3 (retry na timeout)~~ hotovo v bodě 9 výše.
    ✅ L5 (keep_alive) + O9 (širší catch PDF) — OPRAVENO 2026-07-05
12. ✅ O8+V4: jedna validace, jeden počet průchodů — OPRAVENO 2026-07-05
13. O4: slovník žánru (grep) · V6: přístupnost 3.4-6 · MD2: pravdivost stop
14. SC2: topologická variabilita (2–3 vzory + rng)
15. Dokumentační očista: O16–O19, L10–L12, V9–V10, MD5, SZ5

**Stav auditu: DOKONČENO** (všechny moduly projity; tento soubor je průběžný
zápis — položky odškrtávat při realizaci).

---
