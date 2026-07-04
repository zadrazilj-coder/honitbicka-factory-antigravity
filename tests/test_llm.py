"""Testy Ollama klienta s mockovaným transportem (M1) — bez GPU."""

import json

import pytest

from honbicka.llm import (
    DEFAULT_MODEL,
    MAX_RETRY,
    ROLE_CONFIG,
    HonbickaLLMError,
    OllamaKlient,
    Role,
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


def test_generuj_text_bez_schematu():
    def transport(payload, timeout):
        assert "format" not in payload  # volný text nemá structured output
        return _odpoved("Byla jednou jedna louka…")

    klient = OllamaKlient(transport=transport)
    assert klient.generuj_text(Role.VYPRAVEC, "napiš úvod").startswith("Byla")
