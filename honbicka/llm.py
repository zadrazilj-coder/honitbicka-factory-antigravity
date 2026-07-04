"""Ollama klient a role LLM pro HONBIČKA FACTORY.

Jeden model (`qwen3.6:27b`), tři pracovní role + téma-generátor — liší se
system promptem, teplotou, thinking režimem a `num_ctx` (spec §1, §3). Žádné
swapování modelů.

Zásada spec §3: **LLM tvoří, Python rozhoduje.** Tento modul jen volá model;
veškerá herní validace je v `honbicka.validatory`.

Klient je plně mockovatelný přes `transport` (Callable) — testy mimo `@slow`
nikdy nepotřebují GPU ani běžící Ollamu (docs/rozhodnuti.md).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# requests importujeme líně v _http_transport, aby balíček šel importovat
# (a testovat s mockem) i bez nainstalovaného requests.

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.6:27b"
DEFAULT_TIMEOUT_S = 600
MAX_RETRY = 3  # spec §1: 3× retry s opravným promptem, pak tvrdý fail


class HonbickaLLMError(RuntimeError):
    """Tvrdý fail volání LLM (po vyčerpání retry nebo transportní chyba)."""


class Role(StrEnum):
    TEMA_GENERATOR = "tema_generator"
    ARCHITEKT = "architekt"
    VYPRAVEC = "vypravec"
    REDAKTOR = "redaktor"


@dataclass(frozen=True)
class RoleConfig:
    """Parametry role dle spec §1/§3. `system` je základ system promptu
    (plné prompt-inženýrství doplňují M3/M4/M7)."""

    temperature: float
    thinking: bool
    num_ctx: int
    system: str


ROLE_CONFIG: dict[Role, RoleConfig] = {
    # Téma-generátor: thinking OFF, temp 1.0, malý kontext (spec §3.1).
    Role.TEMA_GENERATOR: RoleConfig(
        temperature=1.0,
        thinking=False,
        num_ctx=16384,
        system=(
            "Jsi téma-generátor karetních her HONBIČKA. Navrhni téma, žánr, "
            "prostředí a tón pro dané věkové pásmo. MUSÍŠ se lišit od posledních "
            "her v registru. Odpověz výhradně JSON dle schématu."
        ),
    ),
    # Architekt: thinking ON, temp 0.6, velký kontext (spec §3.2).
    Role.ARCHITEKT: RoleConfig(
        temperature=0.6,
        thinking=True,
        num_ctx=32768,
        system=(
            "Jsi architekt mapy hry HONBIČKA. Z konceptu vyrob mapu jako JSON "
            "graf (uzly, typy, regiony, hrany, podmínky, komponenty). Dodržuj "
            "TVRDÁ omezení (archetyp, práh, pozice AHA, počty). Odpověz jen JSON "
            "dle schématu."
        ),
    ),
    # Vypravěč: thinking OFF, temp 0.85, střední kontext (spec §3.3).
    Role.VYPRAVEC: RoleConfig(
        temperature=0.85,
        thinking=False,
        num_ctx=16384,
        system=(
            "Jsi vypravěč hry HONBIČKA. Píšeš text JEDNÉ karty (přední + zadní "
            "strana) v tvrdém rozpočtu znaků. Atmosférický odstavec je povinný. "
            "Neprozraď víc, než karta smí. Odpověz jen JSON dle schématu."
        ),
    ),
    # Redaktor: thinking ON, temp 0.3, velký kontext (spec §3.4).
    Role.REDAKTOR: RoleConfig(
        temperature=0.3,
        thinking=True,
        num_ctx=32768,
        system=(
            "Jsi redaktor-soudce hry HONBIČKA. Posuzuješ checky R1–R7. Každý "
            "verdikt MUSÍ citovat doslovné úryvky z karet jako důkaz. Odpověz jen "
            "JSON dle schématu."
        ),
    ),
}

# Typ transportu: dostane tělo requestu, vrátí JSON odpověď Ollamy.
Transport = Callable[[dict[str, Any], float], dict[str, Any]]


def _http_transport(payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Výchozí transport: POST na Ollama /api/chat (jediná síťová závislost,
    localhost — spec §12)."""
    import requests  # lokální import: balíček jde importovat i bez requests

    base = payload.pop("_base_url", DEFAULT_BASE_URL)
    resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


class OllamaKlient:
    """Klient k jednomu modelu se třemi rolemi.

    Parametry:
        model: název modelu v Ollamě.
        base_url: adresa Ollama serveru.
        transport: injektovatelná funkce volání (pro testy/mocky).
        timeout_s: timeout jednoho volání.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        transport: Transport | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.transport = transport or _http_transport
        self.timeout_s = timeout_s

    # -- veřejné API ------------------------------------------------------- #
    def generuj_json(
        self,
        role: Role,
        uzivatel: str,
        schema: dict[str, Any],
        extra_system: str | None = None,
    ) -> dict[str, Any]:
        """Zavolá roli se structured outputem (`format` = JSON schema).

        3× zkusí; při nevalidním JSONu přidá opravný prompt. Po vyčerpání
        retry vyhodí `HonbickaLLMError` (spec §1)."""
        cfg = ROLE_CONFIG[role]
        system = cfg.system if not extra_system else f"{cfg.system}\n\n{extra_system}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": uzivatel},
        ]
        posledni_chyba = ""
        for _pokus in range(1, MAX_RETRY + 1):
            odpoved = self._volej(cfg, messages, schema)
            obsah = odpoved.get("message", {}).get("content", "")
            try:
                return json.loads(obsah)
            except (json.JSONDecodeError, TypeError) as exc:
                posledni_chyba = f"{exc}"
                messages.append({"role": "assistant", "content": obsah})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Předchozí odpověď nebyla validní JSON dle schématu "
                            f"({posledni_chyba}). Vrať POUZE validní JSON, nic víc."
                        ),
                    }
                )
        raise HonbickaLLMError(
            f"role {role.value}: nevalidní JSON po {MAX_RETRY} pokusech ({posledni_chyba})"
        )

    def generuj_text(self, role: Role, uzivatel: str, extra_system: str | None = None) -> str:
        """Volné textové volání (bez schématu) — pro role, jejichž výstupem
        jsou volné texty karet, kde nemá smysl structured output."""
        cfg = ROLE_CONFIG[role]
        system = cfg.system if not extra_system else f"{cfg.system}\n\n{extra_system}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": uzivatel},
        ]
        odpoved = self._volej(cfg, messages, schema=None)
        return odpoved.get("message", {}).get("content", "")

    # -- interní ----------------------------------------------------------- #
    def _volej(
        self,
        cfg: RoleConfig,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": cfg.thinking,
            "options": {"temperature": cfg.temperature, "num_ctx": cfg.num_ctx},
            "_base_url": self.base_url,
        }
        if schema is not None:
            payload["format"] = schema
        try:
            return self.transport(payload, self.timeout_s)
        except HonbickaLLMError:
            raise
        except Exception as exc:  # transportní/HTTP chyba → tvrdý fail
            raise HonbickaLLMError(f"transport selhal: {exc}") from exc
