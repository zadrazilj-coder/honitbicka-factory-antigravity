# HONBIČKA 3.4 — DODATKY K ENGINE

> Tyto dodatky **rozšiřují a v konfliktu PŘEBÍJEJÍ** `SKILL.md` (verze 3.3).
> Pořadí autority: **DODATKY_3.4 > SKILL.md**. Nikde jinde se engine nemění.
> Zdroj: zadání HONBIČKA FACTORY, §9. Kde spec mlčí, rozhoduje konzervativní
> default zapsaný do `docs/rozhodnuti.md`.

---

## 3.4-1 · Práh počítadla aktivity — jen násobky 5

Práh počítadla fyzické aktivity (SKILL.md §SYSTÉM NÁPOVĚDY, „losováno 80–120
bodů") se losuje **výhradně v násobcích 5** (80, 85, 90 … 120). Papírové
počítadlo po pětkách jinak práh netrefí.

> Přebíjí: „losuj 80–120 bodů" v SKILL.md → nově „losuj {80,85,…,120}".

## 3.4-2 · Pásmo pozice AHA — parametrizované archetypem a formátem

Pásmo pozice AHA odhalení (SKILL.md §VALIDACE Patro 1 bod 12: „65–80 %")
už není konstanta, ale závisí na archetypu a formátu:

| Podmínka | Pásmo AHA (% mediánového průchodu) |
|---|---|
| Archetyp **A1 / A4 / A7** (objevné) | 65–80 % |
| Archetyp **A2** (kolaps falešného cíle) | 68–85 % |
| Volný sběrový formát (`volny_format`) | horní mez **+7 p. b.** (finální otázka následuje ihned po AHA) |

Archetypy A3, A5, A6 nemají v zadání §9 explicitní pásmo → **konzervativní
default = 65–80 %** (viz `docs/rozhodnuti.md`).

Bonus +7 p. b. u volného formátu se sčítá s pásmem archetypu (např. A2 +
volný formát → 68–92 %).

> Přebíjí: pevné „65–80 %" v SKILL.md.

## 3.4-3 · Pravidlo první návštěvy (volný formát)

Pravidlo „úkol se plní jen při PRVNÍ návštěvě karty" je **povinné** u volného
formátu a patří na herní list. Simulace délky:
- **první návštěva** uzlu → plné tempo (plná časová cena),
- **opakovaný průchod** → ~40 % tempa.

## 3.4-4 · Klíčová svědectví na povinné trase

Klíčová svědectví (stopy nutné k odvození pravdy) musí viset na **POVINNÉ
trase řešení** — za gated předmětem, v povinném světle, za jednosměrkou —
jinak simulace nemůže garantovat pozici AHA. Strojově ověřuje
`validatory/simulace.py` (klíčové svědectví dosažitelné na každé cestě k cíli).

## 3.4-5 · Bezpečnostní jednosměrky se počítají do minim

Bezpečnostní jednosměrky (svah, voda) jsou legitimní topologický prvek a
**počítají se do minim jednosměrek** (SKILL.md §MAPA: „≥2 jednosměrky").

## 3.4-6 · Přístupnost ke klíčovým postavám

K postavám nesoucím klíčové svědectví veď vždy **alespoň jednu fyzicky
nenáročnou hranu** (rodiny s malými dětmi). Strojově: ke každému uzlu typu
`postava` s klíčovým svědectvím existuje ≥1 vstupní hrana bez `high`
fyzického úkolu.

## 3.4-7 · Formát karet A5 (dříve A6)

**Karta = A5 na výšku (148 × 210 mm).** Přebíjí VŠECHNY zmínky „A6" v
SKILL.md (šablony karet, výstupní formát, rozpočet znaků). Tisk, sazba a
fit-check dle zadání §6:
- 2 karty na A4 na výšku nad sebou, vodorovný řez napůl;
- duplex „otáčet po delší straně", zadní strany zůstávají ve stejném svislém
  pořadí (kalibrační arch to ověřuje);
- rozpočet ~1 300–1 500 znaků/strana při 10 pt; atmosférický odstavec
  300–500 znaků je POVINNÝ na přední straně každé karty;
- o vejití na stránku rozhoduje **reálný render (WeasyPrint), ne odhad znaků**
  (rezerva 4 %).

---

## Párování 30/60 (zadání §5) — závazné pro každý princip

Z jednoho herního principu vznikají VŽDY dvě hry: **60min „master"** a
**30min „core"**. Engine profil 90 min se ve factory **nepoužívá**
(konzervativní default — viz `docs/rozhodnuti.md`).

- Architekt staví 60min mapu; každý uzel značí `CORE` nebo `SIDE`.
- CORE podgraf = plnohodnotná 30min hra (onboarding, hlavní osa archetypu,
  všechna povinná svědectví, cíl).
- Validace běží na obou grafech nezávisle (60 = plný, 30 = jen CORE).
- Rozcestníky odkazující na SIDE mají DVĚ varianty zadní strany (60 = plné
  volby, 30 = bez SIDE). Vypravěč píše obě naráz.
- Číslování karet je společné; 30min verze má díry v řadě (průvodce vysvětlí).
- Registr: jeden princip = jeden záznam se dvěma profily.
