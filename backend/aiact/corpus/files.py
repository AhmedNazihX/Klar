"""File helpers shared by the corpus commands (`aiact corpus fetch`, `parse`, `guidelines`)."""

from pathlib import Path


def write_atomic(path: Path, content: bytes) -> None:
    """Write via a temporary file and rename, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(content)
    tmp.replace(path)


def write_if_changed(path: Path, text: str) -> bool:
    """Write `text` atomically unless the file already holds it; True if it was written."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    write_atomic(path, text.encode("utf-8"))
    return True
