"""Testy zatřídění hotové hry do hotove_hry/ (M6)."""

import os

from honbicka.modely import VekPasmo, Zadani
from honbicka.taxonomie import zatrid_hru


def test_zatrid_zaklada_slozky_a_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # hotove_hry/ relativně k cwd
    skin = tmp_path / "skiny" / "lesni-detektivka"
    skin.mkdir(parents=True)
    # simuluj vygenerované PDF
    (skin / "karty_30min.pdf").write_bytes(b"%PDF-1.4 fake")
    (skin / "pruvodce_60min.pdf").write_bytes(b"%PDF-1.4 fake")

    zadani = Zadani(vek=VekPasmo.V06_09, format_hracu="tymy_4x4", tema="Lesní detektivka")
    cesty = zatrid_hru(zadani, "lesni-detektivka", str(skin))

    assert len(cesty) == 2  # 30 i 60 profil
    d30 = "hotove_hry/vek_06-09/tymy_4x4/lesni-detektivka_30min"
    assert os.path.isfile(os.path.join(d30, "INDEX.md"))
    assert os.path.isfile(os.path.join(d30, "karty_30min.pdf"))  # zkopírované
    # INDEX bez spoileru, s pokynem co tisknout
    index = open(os.path.join(d30, "INDEX.md"), encoding="utf-8").read()
    assert "Co vytisknout" in index and "06-09" in index


def test_zatrid_bez_pdf_zaklada_jen_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skin = tmp_path / "skiny" / "hra"
    skin.mkdir(parents=True)
    zadani = Zadani(vek=VekPasmo.V09_12)
    zatrid_hru(zadani, "hra", str(skin))
    d60 = "hotove_hry/vek_09-12/volny_format/hra_60min"
    index = open(os.path.join(d60, "INDEX.md"), encoding="utf-8").read()
    assert "nevygenerováno" in index  # bez PDF (GTK)
