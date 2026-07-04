"""E2E s živým modelem (spec §10) — označeno @slow, přeskočí bez Ollamy.

Ověřuje LLM vrstvu proti reálnému `qwen3.6:27b`: structured output rolí
téma-generátor a architekt-koncept se parsuje do pydantic modelů. Plně validní
živě vygenerovaná hra závisí na kvalitě modelu a ověřuje se ručně (viz README).
"""

import pytest

from honbicka.llm import DEFAULT_BASE_URL, OllamaKlient
from honbicka.modely import Koncept, VekPasmo, Zadani
from honbicka.orchestrator import faze1a_koncept, losuj_parametry, vygeneruj_tema


def _ollama_dostupne() -> bool:
    try:
        import requests
        requests.get(f"{DEFAULT_BASE_URL}/api/tags", timeout=2).raise_for_status()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.slow
skip_bez_ollamy = pytest.mark.skipif(
    not _ollama_dostupne(), reason="Ollama neběží na localhost:11434"
)


@skip_bez_ollamy
def test_zivy_tema_generator_vraci_validni_zadani():
    klient = OllamaKlient(timeout_s=300)
    zadani = vygeneruj_tema(klient, VekPasmo.V06_09, "volny_format", zaznamy=[])
    assert isinstance(zadani, Zadani)
    assert zadani.vek == VekPasmo.V06_09  # plán přepsal věk
    assert zadani.format_hracu == "volny_format"
    assert zadani.tema  # model něco vymyslel


@skip_bez_ollamy
def test_zivy_architekt_koncept_se_parsuje():
    klient = OllamaKlient(timeout_s=300)
    zadani = Zadani(vek=VekPasmo.V06_09, format_hracu="volny_format", tema="cesta kapky vody")
    params = losuj_parametry(zadani, seed=1)
    koncept = faze1a_koncept(klient, zadani, params)
    assert isinstance(koncept, Koncept)
    assert koncept.mechanismus_reseni  # neprázdné řešení
    assert koncept.falesne_teorie >= 0
