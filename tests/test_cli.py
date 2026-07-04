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
