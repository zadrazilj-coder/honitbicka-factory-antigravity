"""Ollama klient a role LLM pro HONBIČKA FACTORY.

Jeden model (`qwen3.6:27b`), čtyři role (`Role` enum: téma-generátor,
architekt, vypravěč, redaktor) — liší se system promptem, teplotou, thinking
režimem a `num_ctx` (spec §1, §3). Žádné swapování modelů.

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
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

# requests importujeme líně v _http_transport, aby balíček šel importovat
# (a testovat s mockem) i bez nainstalovaného requests.

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.6:27b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"  # #8: lokální embeddings pro okna zákazů
DEFAULT_TIMEOUT_S = 600
MAX_RETRY = 3  # spec §1: 3× retry s opravným promptem, pak tvrdý fail

ModelT = TypeVar("ModelT", bound=BaseModel)


class HonbickaLLMError(RuntimeError):
    """Tvrdý fail volání LLM (po vyčerpání retry nebo transportní chyba)."""


class _ThinkingNotSupported(Exception):
    """L2: server odmítl `think` (HTTP 400) — model thinking nepodporuje
    (živě ověřeno sondou `qwen3-coder:30b`, viz docs/rozhodnuti.md)."""


class _PrechodnaChyba(Exception):
    """L3: dočasná transportní chyba (timeout/5xx), kde 1 opakování má smysl —
    na rozdíl od trvalé chyby (4xx krom 400-thinking, DNS, …)."""


class Role(StrEnum):
    TEMA_GENERATOR = "tema_generator"
    ARCHITEKT = "architekt"
    VYPRAVEC = "vypravec"
    REDAKTOR = "redaktor"


@dataclass(frozen=True)
class RoleConfig:
    """Parametry role dle spec §1/§3. `system` je jen základ system promptu —
    plné prompt-inženýrství (kontext, opravné instrukce, příklady) skládají
    volající role-specifické funkce v `orchestrator.py` (`_prompt_vypravec`,
    `_zavolej_architekta`, `faze1a_koncept`)."""

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
    localhost — spec §12). Rozlišuje trvalou chybu od dočasné (L3) a detekuje
    HTTP 400 na `think` u modelu bez podpory thinking (L2)."""
    import requests  # lokální import: balíček jde importovat i bez requests

    base = payload.pop("_base_url", DEFAULT_BASE_URL)
    try:
        resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout_s)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 400 and payload.get("think"):
            raise _ThinkingNotSupported(str(exc)) from exc
        if status is not None and status >= 500:
            raise _PrechodnaChyba(str(exc)) from exc
        raise
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        raise _PrechodnaChyba(str(exc)) from exc
    return resp.json()


def _http_embed(
    base_url: str, model: str, vstupy: list[str], timeout_s: float
) -> list[list[float]]:
    """POST na Ollama /api/embed (#8). Vrací vektory ve stejném pořadí jako `vstupy`."""
    import requests

    resp = requests.post(
        f"{base_url}/api/embed", json={"model": model, "input": vstupy}, timeout=timeout_s
    )
    resp.raise_for_status()
    return resp.json().get("embeddings", [])


DEFAULT_KEEP_ALIVE = "30m"  # L5: Ollama defaultně uvolní model po ~5 min nečinnosti


class OllamaKlient:
    """Klient k jednomu modelu se čtyřmi rolemi.

    Parametry:
        model: název modelu v Ollamě.
        base_url: adresa Ollama serveru.
        transport: injektovatelná funkce volání (pro testy/mocky).
        timeout_s: timeout jednoho volání.
        keep_alive: jak dlouho má Ollama držet model v paměti po posledním
            volání (L5) — mezi hrami v dávce (zápis, validace, sazba) jinak
            hrozí unload→reload (~30 s ztráta na každou další hru).
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        transport: Transport | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.transport = transport or _http_transport
        self.timeout_s = timeout_s
        self.keep_alive = keep_alive
        self.embed_model = embed_model

    def embed(self, texty: list[str]) -> list[list[float]]:
        """Vrátí embeddings textů přes lokální Ollama model (#8, /api/embed).

        Používá se pro sémantická okna zákazů registru (podobnost mechanismů
        řešení). Chyba/nedostupnost embed modelu se propaguje ven — volající
        (`semantika.je_prilis_podobny`) ji chytí a měkce degraduje na přesnou
        shodu, aby generace hry kvůli chybějícímu embed modelu nespadla."""
        if not texty:
            return []
        return _http_embed(self.base_url, self.embed_model, texty, self.timeout_s)

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

    def generuj_model(
        self,
        role: Role,
        uzivatel: str,
        model_cls: type[ModelT],
        schema: dict[str, Any] | None = None,
        extra_system: str | None = None,
    ) -> ModelT:
        """Sjednocené volání: JSON + pydantic validace v JEDNÉ retry smyčce (L1).

        Dřív každé volající místo řešilo pydantic chyby jinak (architekt vracel
        error-tuple, vypravěč měl vlastní retry, koncept/téma tvrdě padaly —
        oba živé pády generace, „čtyři světla" #1 i téma-generátor, by se
        stejnou logikou vyřešily jednotně). 3× zkusí; při nevalidním JSONu NEBO
        neprošlé pydantic validaci přidá cílený opravný prompt s konkrétními
        chybami. Po vyčerpání retry vyhodí `HonbickaLLMError`.

        `schema` default = `model_cls.model_json_schema()`. Nové/legacy volající
        místa s vlastní sémantikou opravy (architekt, vypravěč, koncept —
        game-validity feedback, mechanická poslední záchrana) tuto metodu
        nepoužívají záměrně; viz docs/rozhodnuti.md."""
        cfg = ROLE_CONFIG[role]
        schema = schema if schema is not None else model_cls.model_json_schema()
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
                data = json.loads(obsah)
            except (json.JSONDecodeError, TypeError) as exc:
                posledni_chyba = f"nevalidní JSON: {exc}"
            else:
                try:
                    return model_cls.model_validate(data)
                except ValidationError as exc:
                    posledni_chyba = f"neprošlo validací ({exc.error_count()} chyb): {exc}"
            messages.append({"role": "assistant", "content": obsah})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Předchozí odpověď nevyhověla ({posledni_chyba}). Vrať POUZE "
                        "opravený validní JSON dle schématu, nic víc."
                    ),
                }
            )
        raise HonbickaLLMError(
            f"role {role.value}: nevalidní i po {MAX_RETRY} pokusech ({posledni_chyba})"
        )

    def generuj_text(self, role: Role, uzivatel: str, extra_system: str | None = None) -> str:
        """Volné textové volání (bez schématu, bez `format`).

        Karty i koncept jdou přes `generuj_json`/`generuj_model` (structured
        output) — tahle metoda dnes nemá volající místo v `orchestrator.py`
        (L6: připravené API pro budoucí volně-textovou roli, ne mrtvý kód
        k odstranění — ponecháno záměrně)."""
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
        """L2: pokud model odmítne `think` (HTTP 400), zkusí to jednou znovu
        bez thinking — role s `thinking=False` už tudy neprochází podruhé."""
        try:
            return self._volej_pokus(cfg, messages, schema, cfg.thinking)
        except _ThinkingNotSupported as exc:
            if not cfg.thinking:
                raise HonbickaLLMError(
                    f"transport selhal: model odmítl i volání bez thinking ({exc})"
                ) from exc
            try:
                return self._volej_pokus(cfg, messages, schema, False)
            except _ThinkingNotSupported as exc2:
                raise HonbickaLLMError(
                    f"transport selhal i bez thinking: {exc2}"
                ) from exc2

    def _volej_pokus(
        self,
        cfg: RoleConfig,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None,
        thinking: bool,
    ) -> dict[str, Any]:
        """L3: jedno opakování na dočasnou transportní chybu (timeout/5xx)."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": thinking,
            "options": {"temperature": cfg.temperature, "num_ctx": cfg.num_ctx},
            "keep_alive": self.keep_alive,
            "_base_url": self.base_url,
        }
        if schema is not None:
            payload["format"] = schema
        for pokus in range(2):
            try:
                return self.transport(dict(payload), self.timeout_s)
            except _PrechodnaChyba as exc:
                if pokus == 1:
                    raise HonbickaLLMError(
                        f"transport selhal opakovaně (přechodná chyba): {exc}"
                    ) from exc
                continue
            except _ThinkingNotSupported:
                raise
            except HonbickaLLMError:
                raise
            except Exception as exc:  # ostatní transportní/HTTP chyba → tvrdý fail
                raise HonbickaLLMError(f"transport selhal: {exc}") from exc
        raise AssertionError("nedosažitelné")  # pragma: no cover
