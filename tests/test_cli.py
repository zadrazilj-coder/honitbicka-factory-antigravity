"""Testy CLI (M1 + M7)."""

import os

import pytest
import yaml

from honbicka.cli import main, sestav_yaml, vytvor_parser


def test_status(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "HONBIČKA FACTORY" in out
    assert "Registr:" in out


def test_parser_ma_vsechny_prikazy():
    parser = vytvor_parser()
    assert parser.parse_args(["gen", "zadani/hra.yaml"]).zadani == "zadani/hra.yaml"
    assert parser.parse_args(["batch", "zadani/plan.yaml"]).plan == "zadani/plan.yaml"
    assert parser.parse_args(["feedback", "muj-skin"]).slug == "muj-skin"


def test_feedback_vytvori_sablonu(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = main(["feedback", "moje-hra"])
    assert rc == 0
    assert os.path.isfile("skiny/moje-hra/playtest_vysledky.md")
    text = open("skiny/moje-hra/playtest_vysledky.md", encoding="utf-8").read()
    assert "V kolikáté minutě padlo AHA" in text


def test_sestav_yaml_vynecha_prazdne():
    out = sestav_yaml({"tema": None, "vek": "06-09", "prostredi": [], "ton": "humor"})
    nacteno = yaml.safe_load(out)
    assert nacteno == {"vek": "06-09", "ton": "humor"}  # None a [] vynechány


def test_bez_prikazu_je_chyba():
    with pytest.raises(SystemExit):
        main([])


def test_gen_bez_gtk_failfastuje_pred_llm(tmp_path, monkeypatch, capsys):
    # C1/T2: `honbicka gen` bez GTK musí selhat rychle a čitelně, PŘED
    # jakýmkoli voláním LLM — dřív padalo až uprostřed FÁZE 3 (SazbaNedostupna).
    import honbicka.orchestrator as orch
    monkeypatch.setattr(orch, "je_dostupne", lambda: False)
    monkeypatch.chdir(tmp_path)
    zadani = tmp_path / "hra.yaml"
    zadani.write_text("vek: '09-12'\ntema: Test\n", encoding="utf-8")

    rc = main(["gen", str(zadani)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAILED" in out
    assert "GTK" in out
