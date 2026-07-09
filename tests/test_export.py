"""Testy exportu do .twee (Twine) a Mermaid (analýza §4, doporučení #2)."""

from honbicka.export import export_mermaid, export_twee
from honbicka.modely import Karta, TypUzlu, Volba
from tests.conftest import build_valid_mapa, build_valid_mapa_60


def _karty(mapa):
    def _volby(u):
        return [Volba(text=f"Akce k {h.cil}", vysledek=f"Výsledek {h.cil}", cil=h.cil,
                      podminka=h.podminka)
                for h in u.hrany]
    return [Karta(cislo=u.cislo, nazev=u.nazev, typ=u.typ,
                  atmosfera=f"Atmosféra uzlu {u.cislo}.",
                  uvod=f"Příběh uzlu {u.cislo}.", volby=_volby(u))
            for u in mapa.uzly]


# ------- Twee --------------------------------------------------------------- #
def test_twee_ma_pasaz_pro_kazdy_uzel():
    mapa = build_valid_mapa()
    twee = export_twee(mapa, _karty(mapa), nazev="Kapka")
    for u in mapa.uzly:
        assert f":: {u.cislo} {u.nazev}" in twee
    assert ":: StoryTitle" in twee and "Kapka" in twee
    assert ":: StoryData" in twee  # Twine import bez něj neumí formát


def test_twee_odkazy_odpovidaji_hranam():
    mapa = build_valid_mapa()
    twee = export_twee(mapa, _karty(mapa))
    # uzel 7 → hrany [8, 9]: odkazy vedou na jména pasáží cílů
    assert f"->8 {mapa.uzel(8).nazev}]]" in twee
    assert f"->9 {mapa.uzel(9).nazev}]]" in twee


def test_twee_bez_karet_exportuje_strukturu():
    mapa = build_valid_mapa()
    twee = export_twee(mapa)  # jen mapa (např. FAILED hra bez karet)
    assert f":: 1 {mapa.uzel(1).nazev}" in twee
    assert "->2 " in twee  # hrana 1→2 jako odkaz


def test_twee_znaci_aha_a_profil():
    mapa = build_valid_mapa_60()
    twee = export_twee(mapa, _karty(mapa))
    assert " AHA]" in twee  # AHA uzel má tag
    assert " SIDE]" in twee and " CORE]" in twee


def test_twee_obsahuje_podminku_hrany():
    mapa = build_valid_mapa()
    mapa.uzel(2).hrany[0].podminka = "LUCERNA"
    twee = export_twee(mapa, _karty(mapa))
    assert "(podmínka: LUCERNA)" in twee


# ------- Mermaid ------------------------------------------------------------ #
def test_mermaid_ma_uzly_a_hrany():
    mapa = build_valid_mapa()
    mmd = export_mermaid(mapa)
    assert mmd.startswith("flowchart TD")
    for u in mapa.uzly:
        assert f"n{u.cislo}" in mmd
    assert "n7 --> n8" in mmd and "n7 --> n9" in mmd


def test_mermaid_zvyrazni_aha_a_side():
    mapa = build_valid_mapa_60()
    mmd = export_mermaid(mapa)
    assert f"class n{mapa.pozice_aha_uzel} aha;" in mmd
    side = [f"n{u.cislo}" for u in mapa.uzly if u.profil.value == "SIDE"]
    assert f"class {','.join(side)} side;" in mmd


def test_mermaid_podminka_jako_popisek_hrany():
    mapa = build_valid_mapa()
    mapa.uzel(2).hrany[0].podminka = "KLÍČ"
    mmd = export_mermaid(mapa)
    assert '-->|"KLÍČ"|' in mmd


def test_mermaid_cil_je_kulaty():
    mapa = build_valid_mapa()
    cil = next(u for u in mapa.uzly if u.typ == TypUzlu.CIL)
    assert f"n{cil.cislo}((" in export_mermaid(mapa)


# ------- CLI ---------------------------------------------------------------- #
def test_cli_export_zapise_oba_soubory(tmp_path):
    import json

    from honbicka.cli import main

    mapa = build_valid_mapa()
    skin = tmp_path / "skiny" / "kapka"
    skin.mkdir(parents=True)
    (skin / "mapa.json").write_text(mapa.model_dump_json(), encoding="utf-8")
    (skin / "karty.json").write_text(
        json.dumps([k.model_dump() for k in _karty(mapa)]), encoding="utf-8")
    rc = main(["export", "kapka", "--skiny-dir", str(tmp_path / "skiny")])
    assert rc == 0
    assert (skin / "kapka.twee").is_file()
    assert (skin / "mapa.mmd").is_file()
    assert ":: StoryTitle" in (skin / "kapka.twee").read_text(encoding="utf-8")


def test_cli_export_chybejici_slug_vraci_1(tmp_path, capsys):
    from honbicka.cli import main
    rc = main(["export", "neexistuje", "--skiny-dir", str(tmp_path / "skiny")])
    assert rc == 1
