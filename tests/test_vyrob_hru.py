"""Testy FÁZE 4 (redaktor) a celého stavového stroje vyrob_hru (M6).
Mock klienta rozlišuje roli podle schématu; measurer je fake (bez GTK)."""

import re

from honbicka.modely import Archetyp, Karta, Koncept, StavHry, TypUzlu, VekPasmo, Zadani
from honbicka.orchestrator import (
    REDAKCE_CHECKY,
    _faze4_redaktor_po_jednom,
    _vzorkuj_karty_pro_redakci,
    faze4_redaktor,
    vyrob_hru,
)
from tests.conftest import build_valid_mapa_60


def measurer_dle_delky(html: str, sirka: float) -> float:
    return len(re.sub(r"<[^>]+>", "", html)) / 45.0 * 5.0


KONCEPT_DICT = {
    "archetyp": "A1", "tema": "Kapka vody", "zanr": "přírodní humor",
    "mechanismus_reseni": "průnik tří stop", "klicova_rekvizita": "sítko",
    "falesne_teorie": 2, "pravdive_stopy": 3, "konce": 2, "slovnik_zakazana": [],
}
KARTA_DICT = {
    "cislo": 1, "nazev": "Karta", "typ": "postava", "atmosfera": "A" * 300,
    "predni": "U potoka je vidět stopa vody.", "zadni": "Výsledek.",
}
VERDIKT_DICT = {"check": "R1", "verdikt": True, "citace_karet": ["stopa"], "zduvodneni": "ok"}


class DispatchKlient:
    """Vrací odpověď podle toho, které schéma role žádá."""

    def __init__(self, mapa_dict, *, koncept=None, karta=None, verdikt=None):
        self.mapa_dict = mapa_dict
        self.koncept = koncept or KONCEPT_DICT
        self.karta = karta or KARTA_DICT
        self.verdikt = verdikt or VERDIKT_DICT

    def generuj_json(self, role, uzivatel, schema, extra_system=None):
        props = schema.get("properties", {})
        if "uzly" in props:
            return dict(self.mapa_dict)
        if "atmosfera" in props:
            return dict(self.karta)
        if "falesne_teorie" in props:
            return dict(self.koncept)
        if "citace_karet" in props:
            return dict(self.verdikt)
        raise AssertionError("neznámé schéma")


# ------- FÁZE 4 redaktor: ověřování citací ------------------------------- #
def _karta(cislo, predni):
    from honbicka.modely import Karta, TypUzlu
    return Karta(cislo=cislo, nazev="X", typ=TypUzlu.POSTAVA,
                 atmosfera="Atmosféra.", predni=predni, zadni="Z.")


def test_redaktor_overi_existujici_citaci():
    karty = [_karta(1, "Na kartě je slovo klíč a stopa.")]
    klient = DispatchKlient({}, verdikt={"check": "R1", "verdikt": True,
                                         "citace_karet": ["stopa"], "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert len(verdikty) == 7  # R1..R7
    assert all(v.verdikt for v in verdikty)


def test_redaktor_zneplatni_neexistujici_citaci():
    karty = [_karta(1, "Text bez oné fráze.")]
    klient = DispatchKlient({}, verdikt={"check": "R1", "verdikt": True,
                                         "citace_karet": ["NEEXISTUJE"], "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(not v.verdikt for v in verdikty)
    assert all("citace neověřena" in v.zduvodneni for v in verdikty)


def test_redaktor_overi_citaci_v_uvozovkach():
    # Živě pozorováno (qwen3.6): model citaci obalí uvozovkami — musí to projít.
    karty = [_karta(1, "Rudé světlo zahřeje tvou dlaň, ale mapa ztmavne.")]
    klient = DispatchKlient({}, verdikt={
        "check": "R2", "verdikt": True,
        "citace_karet": ['"Rudé světlo zahřeje tvou dlaň, ale mapa ztmavne."'],
        "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(v.verdikt for v in verdikty)


def test_redaktor_overi_citaci_s_prefixem_cisla_karty():
    # Živě pozorováno: "#1 onboarding 1: "text"" — prefix i uvozovky.
    karty = [_karta(1, "Před tebou se vznášejí čtyři zářivé koule.")]
    klient = DispatchKlient({}, verdikt={
        "check": "R6", "verdikt": True,
        "citace_karet": ['#1 onboarding 1: "Před tebou se vznášejí čtyři zářivé koule."'],
        "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(v.verdikt for v in verdikty)


def test_redaktor_overi_citaci_se_suffixem_za_uvozovkami():
    # Živě pozorováno: "text v uvozovkách" (#1) — suffix po zavírací uvozovce.
    karty = [_karta(1, "Čtyři světla nad tebou čekají na příkaz.")]
    klient = DispatchKlient({}, verdikt={
        "check": "R3", "verdikt": True,
        "citace_karet": ['"Čtyři světla nad tebou čekají na příkaz." (#1)'],
        "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(v.verdikt for v in verdikty)


def test_redaktor_overi_citaci_s_legitimni_elipsou():
    # Živě pozorováno: model spojí dva doslovné úryvky elipsou — každý fragment
    # zvlášť je opravdu z karty, jen mezi nimi model vynechal střed věty.
    karty = [_karta(1, "Rudá jako krev, modrá jako hluboké moře. "
                       "Každý paprsek nese příběh a varování.")]
    klient = DispatchKlient({}, verdikt={
        "check": "R6", "verdikt": True,
        "citace_karet": ['"Rudá jako krev, modrá jako hluboké moře. ... '
                         'Každý paprsek nese příběh a varování."'],
        "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(v.verdikt for v in verdikty)


def test_redaktor_elipsa_s_fabrikovanym_fragmentem_neprojde():
    # Elipsa nesmí být únik pro fabrikaci — jeden fragment musí být reálný,
    # druhý si model vymyslel → celá citace zůstává neplatná.
    karty = [_karta(1, "Rudá jako krev, modrá jako hluboké moře.")]
    klient = DispatchKlient({}, verdikt={
        "check": "R6", "verdikt": True,
        "citace_karet": ['"Rudá jako krev, modrá jako hluboké moře. ... '
                         'toto ve hře vůbec není."'],
        "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(not v.verdikt for v in verdikty)


def test_redaktor_prazdna_citace_je_stale_neplatna():
    # Prázdný seznam citací se nesmí normalizací proměnit v „projde".
    karty = [_karta(1, "Cokoliv.")]
    klient = DispatchKlient({}, verdikt={"check": "R4", "verdikt": True,
                                         "citace_karet": [], "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", 
        mechanismus_reseni="Průnik nezávislých stop odhalí pravdu, ne jediný zdroj.",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(not v.verdikt for v in verdikty)


# ------- celý stavový stroj vyrob_hru ----------------------------------- #
def test_vyrob_hru_uspech(tmp_path):
    mapa_dump = build_valid_mapa_60().model_dump(mode="json")
    klient = DispatchKlient(mapa_dump)
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody")
    hra = vyrob_hru(
        zadani, klient, seed=7, measurer=measurer_dle_delky,
        skiny_dir=str(tmp_path / "skiny"),
        registr_cesta=str(tmp_path / "skiny" / "registr.md"), zatridit=False)

    assert hra.report.stav == StavHry.OK
    assert hra.mapa is not None
    assert len(hra.karty) == 21  # scaffolder staví 21 uzlů
    assert len(hra.report.editorial_report) == 7
    assert hra.report.simulation_reports  # neprázdné
    # PDF krok: bez GTK selže měkce (zaznamenáno), s GTK se vyrenderuje čistě.
    from honbicka.sazba.render import je_dostupne
    if je_dostupne():
        assert not any("PDF nevyrenderováno" in c for c in hra.report.chyby)
        assert (tmp_path / "skiny" / hra.slug / "karty_60min.pdf").is_file()
    else:
        assert any("PDF" in c for c in hra.report.chyby)

    skin = tmp_path / "skiny" / hra.slug
    for f in ("koncept.md", "mapa.json", "karty.json", "report.json", "log.jsonl"):
        assert (skin / f).is_file(), f
    # registr zapsán se seedem
    registr = (tmp_path / "skiny" / "registr.md").read_text(encoding="utf-8")
    assert "| 7 |" in registr and hra.slug in registr


def test_vyrob_hru_failed_kdyz_mapa_neprojde(tmp_path):
    # Legacy LLM-architekt cesta: špatná mapa → FÁZE 1 nekonverguje → FAILED.
    bad = build_valid_mapa_60().model_dump(mode="json")
    bad["pozice_aha_uzel"] = 2  # AHA trvale mimo pásmo
    klient = DispatchKlient(bad)
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody")
    hra = vyrob_hru(zadani, klient, seed=1, measurer=measurer_dle_delky,
                    skiny_dir=str(tmp_path / "skiny"),
                    registr_cesta=str(tmp_path / "skiny" / "registr.md"),
                    zatridit=False, pouzij_scaffolder=False)
    assert hra.report.stav == StavHry.FAILED
    assert hra.mapa is None
    assert (tmp_path / "skiny" / hra.slug / "koncept.md").is_file()


def test_vyrob_hru_scaffolder_je_default(tmp_path):
    # Scaffolder ignoruje (nevalidní) mapu z LLM a přesto vyrobí validní hru.
    bad = build_valid_mapa_60().model_dump(mode="json")
    bad["pozice_aha_uzel"] = 2
    klient = DispatchKlient(bad)
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody")
    hra = vyrob_hru(zadani, klient, seed=1, measurer=measurer_dle_delky,
                    skiny_dir=str(tmp_path / "skiny"),
                    registr_cesta=str(tmp_path / "skiny" / "registr.md"), zatridit=False)
    assert hra.report.stav == StavHry.OK  # scaffolder = spolehlivá FÁZE 1
    assert hra.mapa is not None and len(hra.karty) == 21


# ------- C1/T2: fail-fast bez GTK (PŘED prvním voláním LLM) ---------------- #
class PocitajiciKlient:
    """Klient, který počítá volání — fail-fast nesmí volat LLM ani jednou."""

    def __init__(self):
        self.pocet_volani = 0

    def generuj_json(self, role, uzivatel, schema, extra_system=None):
        self.pocet_volani += 1
        raise AssertionError("fail-fast: LLM nemělo být vůbec voláno")


def test_vyrob_hru_failfast_bez_gtk_nevola_llm(tmp_path, monkeypatch):
    import honbicka.orchestrator as orch
    monkeypatch.setattr(orch, "je_dostupne", lambda: False)
    klient = PocitajiciKlient()
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody")
    hra = vyrob_hru(zadani, klient, seed=1,
                    skiny_dir=str(tmp_path / "skiny"),
                    registr_cesta=str(tmp_path / "skiny" / "registr.md"), zatridit=False)
    assert klient.pocet_volani == 0  # LLM nebylo vůbec zavoláno
    assert hra.report.stav == StavHry.FAILED
    assert hra.mapa is None
    assert any("GTK" in c for c in hra.report.chyby)


def test_vyrob_hru_vlastni_measurer_obejde_failfast(tmp_path, monkeypatch):
    # Vlastní measurer → GTK nepotřeba, fail-fast se nesmí spustit.
    import honbicka.orchestrator as orch
    monkeypatch.setattr(orch, "je_dostupne", lambda: False)
    mapa_dump = build_valid_mapa_60().model_dump(mode="json")
    klient = DispatchKlient(mapa_dump)
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody")
    hra = vyrob_hru(zadani, klient, seed=1, measurer=measurer_dle_delky,
                    skiny_dir=str(tmp_path / "skiny"),
                    registr_cesta=str(tmp_path / "skiny" / "registr.md"), zatridit=False)
    assert hra.report.stav == StavHry.OK


# ------- O9: _pdf_sady chytá libovolnou chybu renderu, ne jen SazbaNedostupna #
def test_vyrob_hru_pdf_jina_vyjimka_nez_sazbanedostupna_je_mekky_fail(tmp_path, monkeypatch):
    """Živě relevantní: chyba fontu/pádu na konkrétní kartě uvnitř WeasyPrintu
    by dřív (jen `except SazbaNedostupna`) shodila celou hru PO drahé LLM
    generaci. Teď je to měkký fail se čitelným důvodem v report.chyby."""
    import honbicka.orchestrator as orch

    def boom(*a, **k):
        raise RuntimeError("font se nenačetl")

    monkeypatch.setattr(orch, "uloz_pdf_karet", boom)
    mapa_dump = build_valid_mapa_60().model_dump(mode="json")
    klient = DispatchKlient(mapa_dump)
    zadani = Zadani(vek=VekPasmo.V09_12, format_hracu="dvojice", tema="Kapka vody")
    hra = vyrob_hru(zadani, klient, seed=1, measurer=measurer_dle_delky,
                    skiny_dir=str(tmp_path / "skiny"),
                    registr_cesta=str(tmp_path / "skiny" / "registr.md"), zatridit=False)
    assert hra.report.stav == StavHry.OK  # jedna vada balíček nešhodí (spec §4)
    assert any("RuntimeError" in c and "font se nenačetl" in c for c in hra.report.chyby)


# ------- L7/O13: jedno sloučené volání + fallback po jednom -------------- #
def _koncept_l7():
    return Koncept(archetyp=Archetyp.A1, tema="Kapka vody",
                   mechanismus_reseni="Průnik nezávislých stop odhalí pravdu.",
                   falesne_teorie=1, pravdive_stopy=2, konce=2)


class JednoVolaniKlient:
    """Vrací všech 7 verdiktů v JEDNOM volání (nové schéma `verdikty`)."""

    def __init__(self, karty_text: str):
        self.pocet_volani = 0
        self.karty_text = karty_text

    def generuj_json(self, role, uzivatel, schema, extra_system=None):
        self.pocet_volani += 1
        props = schema.get("properties", {})
        if "verdikty" not in props:
            raise AssertionError("očekávalo se sloučené schéma s poli 'verdikty'")
        return {"verdikty": [
            {"check": kod, "verdikt": True, "citace_karet": [self.karty_text],
             "zduvodneni": "ok"}
            for kod in REDAKCE_CHECKY
        ]}


def test_faze4_jedno_volani_uspesne_stacilo_jednou():
    karty = [_karta(1, "Na kartě je slovo klíč a stopa.")]
    klient = JednoVolaniKlient("stopa")
    verdikty = faze4_redaktor(klient, karty, _koncept_l7(), Zadani(vek=VekPasmo.V09_12))
    assert klient.pocet_volani == 1  # jedno volání pro všech 7 checků
    assert len(verdikty) == 7
    assert {v.check for v in verdikty} == set(REDAKCE_CHECKY)
    assert all(v.verdikt for v in verdikty)


def test_faze4_chybejici_check_v_odpovedi_se_doplni_jako_failed():
    karty = [_karta(1, "Na kartě je slovo klíč a stopa.")]

    class NeuplnyKlient:
        def generuj_json(self, role, uzivatel, schema, extra_system=None):
            # vrátí jen 5 z 7 (chybí R6, R7)
            return {"verdikty": [
                {"check": kod, "verdikt": True, "citace_karet": ["stopa"], "zduvodneni": "ok"}
                for kod in list(REDAKCE_CHECKY)[:5]
            ]}

    verdikty = faze4_redaktor(NeuplnyKlient(), karty, _koncept_l7(), Zadani(vek=VekPasmo.V09_12))
    assert len(verdikty) == 7
    chybejici = [v for v in verdikty if v.check in ("R6", "R7")]
    assert len(chybejici) == 2
    assert all(not v.verdikt for v in chybejici)
    assert all("chybí v odpovědi" in v.zduvodneni for v in chybejici)


def test_faze4_selhani_slouceneho_volani_spadne_na_po_jednom():
    # DispatchKlient (starý mock) neumí nové schéma → AssertionError → fallback
    karty = [_karta(1, "Na kartě je slovo klíč a stopa.")]
    klient = DispatchKlient({}, verdikt={"check": "R1", "verdikt": True,
                                         "citace_karet": ["stopa"], "zduvodneni": "ok"})
    verdikty = faze4_redaktor(klient, karty, _koncept_l7(), Zadani(vek=VekPasmo.V09_12))
    assert len(verdikty) == 7
    assert all(v.verdikt for v in verdikty)  # fallback per-check taky ověří citaci


def test_faze4_redaktor_po_jednom_prime_volani():
    # přímý test záložní funkce (bez projití hlavní cesty)
    karty = [_karta(1, "Text s frází pravda.")]
    klient = DispatchKlient({}, verdikt={"check": "R1", "verdikt": True,
                                         "citace_karet": ["pravda"], "zduvodneni": "ok"})
    from honbicka.orchestrator import _karty_blob
    blob = _karty_blob(karty)
    verdikty = _faze4_redaktor_po_jednom(klient, blob, _koncept_l7(), Zadani(vek=VekPasmo.V09_12))
    assert len(verdikty) == 7


# ------- O2: vzorkování karet pro redakci --------------------------------- #
def test_vzorkuj_karty_bez_mapy_vraci_vse():
    karty = [Karta(cislo=i, nazev="X", typ=TypUzlu.INFORMACE, atmosfera="A" * 320,
                   predni="p", zadni="z") for i in range(1, 22)]
    assert _vzorkuj_karty_pro_redakci(karty, None) == karty


def test_vzorkuj_karty_vzdy_obsahuje_aha_a_klicove_svedectvi(valid_mapa_60):
    karty = [Karta(cislo=u.cislo, nazev="X", typ=u.typ, atmosfera="A" * 320,
                   predni="p", zadni="z") for u in valid_mapa_60.uzly]
    vzorek = _vzorkuj_karty_pro_redakci(karty, valid_mapa_60, pocet_nahodnych=2)
    cisla_vzorku = {k.cislo for k in vzorek}
    assert valid_mapa_60.pozice_aha_uzel in cisla_vzorku
    for u in valid_mapa_60.uzly:
        if u.klicove_svedectvi:
            assert u.cislo in cisla_vzorku


def test_vzorkuj_karty_je_deterministicky(valid_mapa_60):
    karty = [Karta(cislo=u.cislo, nazev="X", typ=u.typ, atmosfera="A" * 320,
                   predni="p", zadni="z") for u in valid_mapa_60.uzly]
    a = _vzorkuj_karty_pro_redakci(karty, valid_mapa_60, pocet_nahodnych=3)
    b = _vzorkuj_karty_pro_redakci(karty, valid_mapa_60, pocet_nahodnych=3)
    assert [k.cislo for k in a] == [k.cislo for k in b]


def test_vzorkuj_karty_je_serazeny_podle_cisla(valid_mapa_60):
    karty = [Karta(cislo=u.cislo, nazev="X", typ=u.typ, atmosfera="A" * 320,
                   predni="p", zadni="z") for u in valid_mapa_60.uzly]
    vzorek = _vzorkuj_karty_pro_redakci(karty, valid_mapa_60, pocet_nahodnych=3)
    cisla = [k.cislo for k in vzorek]
    assert cisla == sorted(cisla)
