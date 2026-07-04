"""Testy téma-generátoru, YAML zadání/plánů a dávkového běhu (M7)."""

import re

import yaml

from honbicka.davka import BatchPolozka, nacti_plan, nacti_zadani, spust_davku
from honbicka.feedback import nacti_feedbacky, sablona_text, zapis_sablonu
from honbicka.modely import VekPasmo
from honbicka.orchestrator import vygeneruj_tema
from tests.conftest import build_valid_mapa_60


def measurer_dle_delky(html: str, sirka: float) -> float:
    return len(re.sub(r"<[^>]+>", "", html)) / 45.0 * 5.0


ZADANI_DICT = {"tema": "Ledová jeskyně", "vek": "04-06", "format_hracu": "jednotlivci",
               "prostredi": ["les"], "obtiznost": "lehka", "ton": "humor", "jazyk": "cs"}
KONCEPT_DICT = {"archetyp": "A1", "tema": "Kapka vody", "zanr": "humor",
                "mechanismus_reseni": "průnik stop", "klicova_rekvizita": "sítko",
                "falesne_teorie": 2, "pravdive_stopy": 3, "konce": 2, "slovnik_zakazana": []}
KARTA_DICT = {"cislo": 1, "nazev": "K", "typ": "postava", "atmosfera": "A" * 300,
              "predni": "U potoka je stopa.", "zadni": "Výsledek."}
VERDIKT_DICT = {"check": "R1", "verdikt": True, "citace_karet": ["stopa"], "zduvodneni": "ok"}


class DispatchKlient:
    def __init__(self, mapa_dict):
        self.mapa_dict = mapa_dict
        self.prompty: list[str] = []

    def generuj_json(self, role, uzivatel, schema, extra_system=None):
        self.prompty.append(uzivatel)
        props = schema.get("properties", {})
        if "uzly" in props:
            return dict(self.mapa_dict)
        if "atmosfera" in props:
            return dict(KARTA_DICT)
        if "falesne_teorie" in props:
            return dict(KONCEPT_DICT)
        if "citace_karet" in props:
            return dict(VERDIKT_DICT)
        if "format_hracu" in props:  # SCHEMA_ZADANI (téma-generátor)
            return dict(ZADANI_DICT)
        raise AssertionError("neznámé schéma")


# ------- YAML -------------------------------------------------------------- #
def test_nacti_zadani(tmp_path):
    p = tmp_path / "hra.yaml"
    p.write_text(yaml.safe_dump({"vek": "06-09", "tema": "Kapka", "format_hracu": "tymy_4x4"}),
                 encoding="utf-8")
    z = nacti_zadani(str(p))
    assert z.vek == VekPasmo.V06_09 and z.tema == "Kapka"


def test_nacti_plan_seznam_i_dict(tmp_path):
    p1 = tmp_path / "p1.yaml"
    p1.write_text(yaml.safe_dump([{"vek": "06-09", "pocet": 2}]), encoding="utf-8")
    p2 = tmp_path / "p2.yaml"
    p2.write_text(yaml.safe_dump({"hry": [{"vek": "09-12", "format_hracu": "dvojice"}]}),
                  encoding="utf-8")
    assert nacti_plan(str(p1))[0].pocet == 2
    assert nacti_plan(str(p2))[0].format_hracu == "dvojice"


# ------- téma-generátor ---------------------------------------------------- #
def test_vygeneruj_tema_prepise_vek_a_format():
    klient = DispatchKlient({})
    z = vygeneruj_tema(klient, VekPasmo.V12_15, "tymy_3x3", zaznamy=[])
    # LLM vrátil vek 04-06 / jednotlivci, ale plán řídí → přepsáno
    assert z.vek == VekPasmo.V12_15
    assert z.format_hracu == "tymy_3x3"
    assert z.tema == "Ledová jeskyně"


def test_vygeneruj_tema_robustni_vuci_nedokonalemu_modelu():
    """Reálný model vrací i diakritiku ('těžká') a vynechá vek — pipeline to
    ustojí (regrese z živého E2E)."""
    class Messy:
        def generuj_json(self, role, uzivatel, schema, extra_system=None):
            return {"tema": "Pohádka", "prostredi": ["les"],
                    "obtiznost": "těžká", "ton": "hravý", "jazyk": "cs"}  # bez 'vek'

    z = vygeneruj_tema(Messy(), VekPasmo.V09_12, "dvojice", zaznamy=[])
    assert z.vek == VekPasmo.V09_12
    assert z.obtiznost.value == "tezka"  # diakritika normalizována


# ------- feedback ---------------------------------------------------------- #
def test_feedback_sablona_a_cteni(tmp_path):
    cesta = zapis_sablonu("hra-x", str(tmp_path))
    assert cesta.endswith("playtest_vysledky.md")
    # prázdná šablona se nečte jako vyplněná
    assert nacti_feedbacky(str(tmp_path)) == []
    # vyplníme odpověď
    with open(cesta, "w", encoding="utf-8") as f:
        f.write(sablona_text("hra-x").replace("> ", "> AHA padlo v 40. minutě", 1))
    assert len(nacti_feedbacky(str(tmp_path))) == 1


# ------- dávka ------------------------------------------------------------- #
def test_spust_davku_uspech(tmp_path):
    klient = DispatchKlient(build_valid_mapa_60().model_dump(mode="json"))
    plan = [BatchPolozka(vek=VekPasmo.V09_12, format_hracu="dvojice", pocet=2)]
    report = spust_davku(plan, klient, measurer=measurer_dle_delky,
                         skiny_dir=str(tmp_path / "skiny"),
                         registr_cesta=str(tmp_path / "skiny" / "registr.md"),
                         zatridit=False)
    assert report.celkem == 2
    assert report.uspesnych == 2


def test_spust_davku_failed_nezastavi(tmp_path):
    from honbicka.llm import HonbickaLLMError

    class RaisingKlient:
        def generuj_json(self, role, uzivatel, schema, extra_system=None):
            raise HonbickaLLMError("model nedostupný")

    plan = [BatchPolozka(vek=VekPasmo.V09_12, format_hracu="dvojice", pocet=3)]
    report = spust_davku(plan, RaisingKlient(), measurer=measurer_dle_delky,
                         skiny_dir=str(tmp_path / "skiny"),
                         registr_cesta=str(tmp_path / "skiny" / "registr.md"),
                         zatridit=False)
    assert report.celkem == 3  # dávka doběhla celá i přes chyby
    assert report.failed == 3
