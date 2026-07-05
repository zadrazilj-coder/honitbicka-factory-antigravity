"""Testy Ollama klienta s mockovaným transportem (M1) — bez GPU."""

import json

import pytest
from pydantic import BaseModel, Field

from honbicka.llm import (
    DEFAULT_MODEL,
    MAX_RETRY,
    ROLE_CONFIG,
    HonbickaLLMError,
    OllamaKlient,
    Role,
    _PrechodnaChyba,
    _ThinkingNotSupported,
)
from honbicka.modely import SCHEMA_ZADANI


def _odpoved(obsah: str) -> dict:
    return {"message": {"role": "assistant", "content": obsah}}


def test_role_config_dle_spec():
    # spec §1/§3: teploty, thinking, num_ctx
    assert ROLE_CONFIG[Role.TEMA_GENERATOR].temperature == 1.0
    assert ROLE_CONFIG[Role.TEMA_GENERATOR].thinking is False
    assert ROLE_CONFIG[Role.ARCHITEKT].temperature == 0.6
    assert ROLE_CONFIG[Role.ARCHITEKT].thinking is True
    assert ROLE_CONFIG[Role.ARCHITEKT].num_ctx == 32768
    assert ROLE_CONFIG[Role.VYPRAVEC].temperature == 0.85
    assert ROLE_CONFIG[Role.VYPRAVEC].num_ctx == 16384
    assert ROLE_CONFIG[Role.REDAKTOR].temperature == 0.3
    assert ROLE_CONFIG[Role.REDAKTOR].thinking is True
    assert ROLE_CONFIG[Role.REDAKTOR].num_ctx == 32768


def test_generuj_json_uspech():
    zachyceno = {}

    def transport(payload, timeout):
        zachyceno.update(payload)
        return _odpoved(json.dumps({"vek": "06-09", "format_hracu": "volny_format"}))

    klient = OllamaKlient(transport=transport)
    out = klient.generuj_json(Role.TEMA_GENERATOR, "navrhni téma", SCHEMA_ZADANI)
    assert out["vek"] == "06-09"
    # payload nese model, schema, think, options
    assert zachyceno["model"] == DEFAULT_MODEL
    assert zachyceno["format"] == SCHEMA_ZADANI
    assert zachyceno["think"] is False
    assert zachyceno["options"]["temperature"] == 1.0
    assert zachyceno["stream"] is False


def test_generuj_json_retry_pak_uspech():
    pokusy = {"n": 0}

    def transport(payload, timeout):
        pokusy["n"] += 1
        if pokusy["n"] == 1:
            return _odpoved("tohle není JSON")
        return _odpoved(json.dumps({"vek": "09-12"}))

    klient = OllamaKlient(transport=transport)
    out = klient.generuj_json(Role.ARCHITEKT, "postav mapu", SCHEMA_ZADANI)
    assert out["vek"] == "09-12"
    assert pokusy["n"] == 2  # jeden retry


def test_generuj_json_tvrdy_fail_po_retry():
    volani = {"n": 0}

    def transport(payload, timeout):
        volani["n"] += 1
        return _odpoved("pořád ne JSON")

    klient = OllamaKlient(transport=transport)
    with pytest.raises(HonbickaLLMError):
        klient.generuj_json(Role.VYPRAVEC, "napiš kartu", SCHEMA_ZADANI)
    assert volani["n"] == MAX_RETRY  # 3× a dost


def test_transportni_chyba_je_tvrdy_fail():
    def transport(payload, timeout):
        raise ConnectionError("Ollama neběží")

    klient = OllamaKlient(transport=transport)
    with pytest.raises(HonbickaLLMError):
        klient.generuj_json(Role.ARCHITEKT, "x", SCHEMA_ZADANI)


# --------------------------------------------------------------------------- #
# L5 — keep_alive (mezi hrami v dávce se model nesmí uvolnit z paměti)
# --------------------------------------------------------------------------- #
def test_keep_alive_v_payloadu_ma_vychozi_hodnotu():
    zachyceno = {}

    def transport(payload, timeout):
        zachyceno.update(payload)
        return _odpoved(json.dumps({}))

    klient = OllamaKlient(transport=transport)
    klient.generuj_json(Role.TEMA_GENERATOR, "x", SCHEMA_ZADANI)
    assert zachyceno["keep_alive"] == "30m"


def test_keep_alive_lze_prepsat():
    zachyceno = {}

    def transport(payload, timeout):
        zachyceno.update(payload)
        return _odpoved(json.dumps({}))

    klient = OllamaKlient(transport=transport, keep_alive="5m")
    klient.generuj_json(Role.TEMA_GENERATOR, "x", SCHEMA_ZADANI)
    assert zachyceno["keep_alive"] == "5m"


def test_generuj_text_bez_schematu():
    def transport(payload, timeout):
        assert "format" not in payload  # volný text nemá structured output
        return _odpoved("Byla jednou jedna louka…")

    klient = OllamaKlient(transport=transport)
    assert klient.generuj_text(Role.VYPRAVEC, "napiš úvod").startswith("Byla")


# --------------------------------------------------------------------------- #
# L1 — generuj_model (JSON + pydantic v jedné retry smyčce)
# --------------------------------------------------------------------------- #
class _Prosty(BaseModel):
    jmeno: str = Field(min_length=2)
    vek: int


def test_generuj_model_uspech():
    def transport(payload, timeout):
        return _odpoved(json.dumps({"jmeno": "Ana", "vek": 7}))

    klient = OllamaKlient(transport=transport)
    out = klient.generuj_model(Role.TEMA_GENERATOR, "x", _Prosty)
    assert isinstance(out, _Prosty)
    assert out.jmeno == "Ana" and out.vek == 7


def test_generuj_model_retry_po_nevalidnim_json():
    pokusy = {"n": 0}

    def transport(payload, timeout):
        pokusy["n"] += 1
        if pokusy["n"] == 1:
            return _odpoved("tohle není JSON")
        return _odpoved(json.dumps({"jmeno": "Béďa", "vek": 9}))

    klient = OllamaKlient(transport=transport)
    out = klient.generuj_model(Role.TEMA_GENERATOR, "x", _Prosty)
    assert out.vek == 9
    assert pokusy["n"] == 2


def test_generuj_model_retry_po_pydantic_chybe():
    """Chybějící/nevalidní pole projde JSON parserem, ale spadne na validaci
    modelu — i to musí odpálit opravný prompt (na rozdíl od `generuj_json`,
    který pydantic vůbec neřeší)."""
    pokusy = {"n": 0}

    def transport(payload, timeout):
        pokusy["n"] += 1
        if pokusy["n"] == 1:
            # jmeno krátké, vek špatný typ
            return _odpoved(json.dumps({"jmeno": "A", "vek": "neco"}))
        return _odpoved(json.dumps({"jmeno": "Cecilka", "vek": 5}))

    klient = OllamaKlient(transport=transport)
    out = klient.generuj_model(Role.TEMA_GENERATOR, "x", _Prosty)
    assert out.jmeno == "Cecilka"
    assert pokusy["n"] == 2


def test_generuj_model_tvrdy_fail_po_vycerpani():
    def transport(payload, timeout):
        return _odpoved(json.dumps({"jmeno": "A", "vek": 1}))  # jmeno pořád moc krátké

    klient = OllamaKlient(transport=transport)
    with pytest.raises(HonbickaLLMError):
        klient.generuj_model(Role.TEMA_GENERATOR, "x", _Prosty)


# --------------------------------------------------------------------------- #
# L2 — fallback bez thinking, když model HTTP 400 na `think`
# --------------------------------------------------------------------------- #
def test_volej_zkusi_bez_thinking_kdyz_model_odmitne():
    pokusy = []

    def transport(payload, timeout):
        pokusy.append(payload["think"])
        if payload["think"]:
            raise _ThinkingNotSupported("HTTP 400")
        return _odpoved(json.dumps({"vek": "06-09"}))

    klient = OllamaKlient(transport=transport)
    # ARCHITEKT má thinking=True v ROLE_CONFIG
    out = klient.generuj_json(Role.ARCHITEKT, "x", SCHEMA_ZADANI)
    assert out["vek"] == "06-09"
    assert pokusy == [True, False]


def test_volej_bez_thinking_odmitnuti_je_tvrdy_fail():
    def transport(payload, timeout):
        raise _ThinkingNotSupported("HTTP 400")

    klient = OllamaKlient(transport=transport)
    # VYPRAVEC má thinking=False → není kam ustoupit
    with pytest.raises(HonbickaLLMError):
        klient.generuj_json(Role.VYPRAVEC, "x", SCHEMA_ZADANI)


def test_volej_odmitnuti_i_bez_thinking_je_tvrdy_fail():
    def transport(payload, timeout):
        raise _ThinkingNotSupported("HTTP 400")

    klient = OllamaKlient(transport=transport)
    with pytest.raises(HonbickaLLMError):
        klient.generuj_json(Role.ARCHITEKT, "x", SCHEMA_ZADANI)


# --------------------------------------------------------------------------- #
# L3 — jedno opakování na dočasnou transportní chybu
# --------------------------------------------------------------------------- #
def test_volej_opakuje_na_prechodnou_chybu():
    pokusy = {"n": 0}

    def transport(payload, timeout):
        pokusy["n"] += 1
        if pokusy["n"] == 1:
            raise _PrechodnaChyba("timeout")
        return _odpoved(json.dumps({"vek": "06-09"}))

    klient = OllamaKlient(transport=transport)
    out = klient.generuj_json(Role.TEMA_GENERATOR, "x", SCHEMA_ZADANI)
    assert out["vek"] == "06-09"
    assert pokusy["n"] == 2


def test_volej_prechodna_chyba_dvakrat_je_tvrdy_fail():
    def transport(payload, timeout):
        raise _PrechodnaChyba("timeout")

    klient = OllamaKlient(transport=transport)
    with pytest.raises(HonbickaLLMError):
        klient.generuj_json(Role.TEMA_GENERATOR, "x", SCHEMA_ZADANI)


# --------------------------------------------------------------------------- #
# L2/L3 — mapování HTTP chyb ve výchozím _http_transport
# --------------------------------------------------------------------------- #
def test_http_transport_400_s_think_je_thinking_not_supported(monkeypatch):
    import requests

    from honbicka.llm import _http_transport

    class FakeResp:
        status_code = 400

        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(_ThinkingNotSupported):
        _http_transport({"think": True, "_base_url": "http://x"}, 1.0)


def test_http_transport_5xx_je_prechodna_chyba(monkeypatch):
    import requests

    from honbicka.llm import _http_transport

    class FakeResp:
        status_code = 503

        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(_PrechodnaChyba):
        _http_transport({"think": False, "_base_url": "http://x"}, 1.0)


def test_http_transport_timeout_je_prechodna_chyba(monkeypatch):
    import requests

    from honbicka.llm import _http_transport

    def raiser(*a, **k):
        raise requests.exceptions.Timeout("pomalé")

    monkeypatch.setattr(requests, "post", raiser)
    with pytest.raises(_PrechodnaChyba):
        _http_transport({"think": False, "_base_url": "http://x"}, 1.0)


def test_http_transport_400_bez_think_neni_zvlastni_chyba(monkeypatch):
    """400 bez `think` v payloadu je trvalá chyba (např. špatné schéma) —
    nemá se plést s L2 fallbackem."""
    import requests

    from honbicka.llm import _http_transport

    class FakeResp:
        status_code = 400

        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(requests.exceptions.HTTPError):
        _http_transport({"think": False, "_base_url": "http://x"}, 1.0)
