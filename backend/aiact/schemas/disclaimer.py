"""The "guidance, not legal advice" notice every result and tool output carries."""

from collections.abc import Mapping
from types import MappingProxyType

from aiact.schemas.enums import Language

DISCLAIMER_EN = (
    "This is guidance, not legal advice. It is based only on the description provided and "
    "the version of the AI Act shown. Have decisions with legal consequences reviewed by a lawyer."
)

DISCLAIMER_DE = (
    "Dies ist eine Orientierungshilfe, keine Rechtsberatung. Sie beruht ausschließlich auf der "
    "angegebenen Beschreibung und der angezeigten Fassung der KI-Verordnung. Lassen Sie "
    "Entscheidungen mit rechtlicher Tragweite anwaltlich prüfen."
)

DISCLAIMER: Mapping[Language, str] = MappingProxyType(
    {Language.EN: DISCLAIMER_EN, Language.DE: DISCLAIMER_DE}
)
"""The notice per language (read-only)."""
