"""HONBIČKA FACTORY — autonomní generátor venkovních karetních her.

Engine (herní mechanika) je v ``engine/SKILL.md`` + ``engine/DODATKY_3.4.md``
a je jediným zdrojem pravdy; tento balíček ho jen provádí, nikdy neobchází.
"""

__version__ = "0.1.0"

from honbicka import modely
from honbicka.llm import HonbickaLLMError, OllamaKlient, Role

__all__ = ["modely", "OllamaKlient", "Role", "HonbickaLLMError", "__version__"]
