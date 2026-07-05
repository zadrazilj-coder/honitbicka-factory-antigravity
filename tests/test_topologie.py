"""Testy topologických kontrol na ručně rozbitých grafech (M2)."""

from honbicka.modely import Hrana, TypUzlu
from honbicka.validatory.topologie import zkontroluj_topologii


def test_valid_projde(valid_mapa):
    v = zkontroluj_topologii(valid_mapa)
    assert v.ok, v.chyby


def test_osirely_uzel(valid_mapa):
    # odpojíme uzel 4 (nikdo na něj nemíří) — musí zůstat dosažitelný odjinud;
    # nejdřív smažeme hranu 2→4, čímž se 4 stane osiřelým
    valid_mapa.uzel(2).hrany = [Hrana(cil=3)]
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("osiřel" in c for c in v.chyby)


def test_softlock_bez_vychodu(valid_mapa):
    valid_mapa.uzel(8).hrany = []  # ne-cil bez východu
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("softlock" in c or "východ" in c for c in v.chyby)


def test_nedosahne_cil(valid_mapa):
    # uzel 8 pošleme zpět do 7 místo do cíle → z 8 už nevede cesta k cíli
    valid_mapa.uzel(8).hrany = [Hrana(cil=7)]
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("nemůže se vrátit" in c or "cíl" in c.lower() for c in v.chyby)


def test_dve_sber_za_sebou(valid_mapa):
    valid_mapa.uzel(3).typ = TypUzlu.SBER
    valid_mapa.uzel(5).typ = TypUzlu.SBER  # 3→5 obě sber
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("sber" in c for c in v.chyby)


def test_prazdna_volba(valid_mapa):
    # dvě hrany se shodným cílem i efektem
    valid_mapa.uzel(2).hrany = [Hrana(cil=3, efekt="jdi"), Hrana(cil=3, efekt="jdi")]
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("prázdná volba" in c for c in v.chyby)


def test_hrana_na_neexistujici(valid_mapa):
    valid_mapa.uzel(2).hrany.append(Hrana(cil=999))
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("neexistující" in c for c in v.chyby)


def test_chybi_cil(valid_mapa):
    valid_mapa.uzel(11).typ = TypUzlu.POSTAVA  # už žádný cil
    valid_mapa.uzel(11).hrany = [Hrana(cil=1)]
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("cil" in c.lower() for c in v.chyby)


# ------- V6: dodatek 3.4-6 (přístupnost) ----------------------------------- #
def test_klicove_svedectvi_bez_nenarocne_vstupni_hrany(valid_mapa):
    # uzel 8 nese klíčové svědectví; jediná vstupní hrana je 7→8 — udělej ji "high"
    hrana_do_8 = next(h for h in valid_mapa.uzel(7).hrany if h.cil == 8)
    hrana_do_8.fyzicka_narocnost = "high"
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("klíčové svědectví" in c and "8" in c for c in v.chyby)


def test_klicove_svedectvi_s_nenarocnou_vstupni_hranou_projde(valid_mapa):
    # výchozí fixtura: hrana 7→8 je defaultně "low" → V6 neshledá problém
    v = zkontroluj_topologii(valid_mapa)
    assert v.ok, v.chyby


def test_klicove_svedectvi_staci_jedna_nenarocna_z_vice_vstupnich(valid_mapa):
    # 2. vstupní hrana do 8 (9→8, vedle existující 7→8) je "high" — pořád OK,
    # protože 7→8 zůstává "low"
    valid_mapa.uzel(9).hrany.append(Hrana(cil=8, fyzicka_narocnost="high"))
    v = zkontroluj_topologii(valid_mapa)
    assert v.ok, v.chyby


def test_topologicka_minima_linearni_mapa(valid_mapa):
    # zrušíme smyčku/slepou/jednosměrku → nesplní minima
    valid_mapa.uzel(9).typ = TypUzlu.PRECHOD   # zruší slepou
    valid_mapa.uzel(10).typ = TypUzlu.PRECHOD  # zruší smyčku
    valid_mapa.uzel(10).hrany[0].jednosmerna = False  # zruší jednosměrku (10→11)
    v = zkontroluj_topologii(valid_mapa)
    assert not v.ok
    assert any("smyček" in c or "slepých" in c or "jednosměrek" in c for c in v.chyby)
