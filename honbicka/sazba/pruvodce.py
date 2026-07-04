"""Průvodce organizátora A4 (spec §6): spoiler přehled, správná odpověď,
rozmístění, stavěcí checklist, brífink doslovně, EPILOG k přečtení nahlas,
pocty/diplomy, QA + redakční posudek s citacemi, feedback formulář, tisková
instrukce, příloha s obsahem karet."""

from __future__ import annotations

import html as _html

from honbicka.modely import Karta, Koncept, Mapa, RedakceVerdikt, Zadani

# 5 otázek feedback formuláře (spec §6, doslovně).
FEEDBACK_OTAZKY = [
    "V kolikáté minutě padlo AHA odhalení?",
    "Kde se hráči zasekli?",
    "Čemu se nejvíc smáli?",
    "Co bylo moc těžké / moc lehké?",
    "Hráli by znovu?",
]

# Stavěcí checklist — doslovné znění časů (spec §6).
CHECKLIST = [
    ("Obhlídka terénu", "5 min"),
    ("Mapování uzlů na konkrétní místa", "5 min"),
    ("Rozmístění karet", "5 min"),
    ("Brífink hráčů", "1 min"),
]


def _sekce(nadpis: str, obsah: str, trida: str = "") -> str:
    t = f" class='{trida}'" if trida else ""
    return f"<section{t}><h2>{_html.escape(nadpis)}</h2>{obsah}</section>"


def _epilog_default(koncept: Koncept, format_hracu: str) -> str:
    vyhodnoceni = {
        "dvojice": "Přečtěte nahlas zapsané teorie dvojic a porovnejte s pravdou.",
        "jednotlivci": "Zeptejte se, kdo se pravdě přiblížil.",
    }.get(format_hracu, "Vyhlaste vsazené teorie týmů veřejně a s humorem, bez ponižování.")
    if format_hracu.startswith("tymy_"):
        vyhodnoceni = "Vyhlaste vsazené teorie týmů veřejně a s humorem, bez ponižování."
    return (
        f"<p><b>Co se doopravdy dělo:</b> {_html.escape(koncept.mechanismus_reseni)}</p>"
        f"<p><b>Mapa lží:</b> které stopy byly pravdivé a kdo (a proč) lhal — projděte "
        f"s hráči nahlas.</p>"
        f"<p><b>Vyhodnocení teorií:</b> {vyhodnoceni}</p>"
        f"<p><b>Vyhlášení a diplomy:</b> dosažené vrstvy vítězství, nejvíc pohybu, "
        f"nejlepší grimasa, nejodvážnější teorie.</p>"
    )


def postav_html_pruvodce(
    *,
    koncept: Koncept,
    zadani: Zadani,
    mapa: Mapa,
    karty: list[Karta],
    prah: int,
    editorial: list[RedakceVerdikt] | None = None,
    brifink: str | None = None,
    epilog: str | None = None,
) -> str:
    esc = _html.escape

    spoiler = (
        f"<p><b>Archetyp zvratu:</b> {koncept.archetyp.value}</p>"
        f"<p><b>Mechanismus řešení:</b> {esc(koncept.mechanismus_reseni)}</p>"
        f"<p><b>Klíčová rekvizita:</b> {esc(koncept.klicova_rekvizita or '—')}</p>"
    )
    odpoved = (
        f"<p>{esc(koncept.mechanismus_reseni)}</p>"
        f"<p>Pravda se odvozuje průnikem stop ({koncept.pravdive_stopy} pravdivých); "
        f"žádný jednotlivý zdroj ji neprozradí.</p>"
    )
    rozmisteni = "<ul>" + "".join(
        f"<li>#{u.cislo} {esc(u.nazev)} — {u.typ.value}, region {esc(u.region)}</li>"
        for u in sorted(mapa.uzly, key=lambda u: u.cislo)
    ) + "</ul>"
    checklist = "<ol>" + "".join(
        f"<li>{esc(k)} — <b>{esc(t)}</b></li>" for k, t in CHECKLIST
    ) + "</ol>"
    brifink_txt = brifink or (
        f"Situace: {esc(koncept.tema)}. Nikdo vám nedává úkol — rozhlédněte se a zjistěte, "
        "co se děje. Karty jsou v terénu; přebíhejte mezi nimi."
    )
    epilog_txt = epilog or _epilog_default(koncept, zadani.format_hracu)
    zasah = (
        f"<p>Počítadlo má práh {prah}. Pokud nikdo neodhalí pravdu do ~80 % času, pošlete "
        "postavu nápovědy sama za hráči. Rádce smí říct „kam se vrátit“, nikdy „proč“.</p>"
    )

    if editorial:
        polozky = []
        for v in editorial:
            stav = "OK" if v.verdikt else "CHYBA"
            citace = ""
            if v.citace_karet:
                citace = " citace: " + "; ".join(f"„{esc(c)}“" for c in v.citace_karet)
            polozky.append(
                f"<li><b>{esc(v.check)}: {stav}</b> — {esc(v.zduvodneni)}{citace}</li>"
            )
        redakce = "<ul>" + "".join(polozky) + "</ul>"
    else:
        redakce = "<p>Redakční posudek se doplní ve FÁZI 4.</p>"

    feedback = "<ol>" + "".join(f"<li>{esc(o)}</li>" for o in FEEDBACK_OTAZKY) + "</ol>"
    tisk = (
        "<p>Karty: A4 na šířku, 2 karty A5 na výšku vedle sebe, svislý řez uprostřed. "
        "Duplex „otáčet po delší straně“. Nejdřív vytiskni KALIBRAČNÍ arch (strana 1–2) "
        "a ověř zákryt proti světlu. Herní list A5, tento průvodce A4.</p>"
    )
    priloha = "".join(
        f"<div><b>#{k.cislo} {esc(k.nazev)}</b><p><i>{esc(k.atmosfera)}</i></p>"
        f"<p>{esc(k.predni)}</p><p>[zadní] {esc(k.zadni)}</p></div>"
        for k in sorted(karty, key=lambda k: k.cislo)
    )

    telo = (
        f"<h1>Průvodce organizátora — {esc(koncept.tema)}</h1>"
        + _sekce("Spoiler přehled", spoiler, "spoiler")
        + _sekce("Správná odpověď", odpoved)
        + _sekce("Rozmístění uzlů", rozmisteni)
        + _sekce("Stavěcí checklist", checklist)
        + _sekce("Brífink (přečtěte doslovně)", f"<p>{brifink_txt}</p>")
        + _sekce("EPILOG — přečtěte nahlas všem", epilog_txt, "epilog")
        + _sekce("Kdy zasáhnout", zasah)
        + _sekce("QA a redakční posudek", redakce)
        + _sekce("Feedback formulář (5 otázek)", feedback)
        + _sekce("Tisková instrukce", tisk)
        + _sekce("Příloha — obsah karet (náhrada za ztracenou)", priloha)
    )
    from honbicka.sazba.styl import CSS_A4_PRUVODCE
    return (
        f"<html><head><meta charset='utf-8'><style>{CSS_A4_PRUVODCE}</style></head>"
        f"<body>{telo}</body></html>"
    )
