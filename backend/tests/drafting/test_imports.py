"""Drafting stands on the result contract alone: importing it never loads the engine."""

import subprocess
import sys

PROBE = (
    "import sys, aiact.drafting; "
    "print(sorted(m for m in sys.modules if m == 'aiact.engine' or m.startswith('aiact.engine.')))"
)


def test_importing_drafting_does_not_load_the_engine() -> None:
    probe = subprocess.run(
        [sys.executable, "-c", PROBE], capture_output=True, text=True, check=True
    )
    assert probe.stdout.strip() == "[]"
