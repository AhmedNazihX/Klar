"""File helpers shared by the corpus commands (`aiact corpus fetch`, `aiact corpus parse`)."""

from pathlib import Path


def write_atomic(path: Path, content: bytes) -> None:
    """Write via a temporary file and rename, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(content)
    tmp.replace(path)
