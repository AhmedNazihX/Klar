"""Klar on paper: the colours (the design system's tokens) and the assets both renderers use."""

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
LOGO_PNG = ASSETS / "klar-lockup-flat.png"
"""The flat lockup, the design system's logo for print, Word and PDF (see assets/README.md)."""
FONTS = ASSETS / "fonts"

INK = "#0F1B2D"
INK_2 = "#1B2A44"
SLATE = "#4A5670"
LENS_BLUE = "#2D4BE0"
FILL_TINT = "#EEF1FD"
"""Lens blue at 7% on white: the ground of a "To fill in" marker."""
QUOTE_TINT = "#F3F5F9"
STAMP = "#873A00"
"""The DRAFT stamp's colour (the draft StatusPill)."""

LOGO_WIDTH_MM = 32.0
LOGO_HEIGHT_MM = LOGO_WIDTH_MM * 1182 / 3452.9
"""The lockup's own proportions (its viewBox, 3452.9 by 1182)."""
MARGIN_MM = 20.0


def rgb(colour: str) -> tuple[int, int, int]:
    """A `#RRGGBB` colour as its three channels."""
    value = int(colour.removeprefix("#"), 16)
    return value >> 16, (value >> 8) & 0xFF, value & 0xFF
