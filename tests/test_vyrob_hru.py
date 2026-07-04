"""Testy FÁZE 4 (redaktor) a celého stavového stroje vyrob_hru (M6).
Mock klienta rozlišuje roli podle schématu; measurer je fake (bez GTK)."""

import re

from honbicka.modely import Archetyp, Koncept, StavHry, VekPasmo, Zadani
from honbicka.orchestrator import faze4_redaktor, vyrob_hru
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
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", mechanismus_reseni="m",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert len(verdikty) == 7  # R1..R7
    assert all(v.verdikt for v in verdikty)


def test_redaktor_zneplatni_neexistujici_citaci():
    karty = [_karta(1, "Text bez oné fráze.")]
    klient = DispatchKlient({}, verdikt={"check": "R1", "verdikt": True,
                                         "citace_karet": ["NEEXISTUJE"], "zduvodneni": "ok"})
    koncept = Koncept(archetyp=Archetyp.A1, tema="X", mechanismus_reseni="m",
                      falesne_teorie=1, pravdive_stopy=2, konce=2)
    verdikty = faze4_redaktor(klient, karty, koncept, Zadani(vek=VekPasmo.V09_12))
    assert all(not v.verdikt for v in verdikty)
    assert all("citace neověřena" in v.zduvodneni for v in verdikty)


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
    # bez GTK se PDF nevyrenderuje → zaznamenáno, ale hra je datově platná
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
