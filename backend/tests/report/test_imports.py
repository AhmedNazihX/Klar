"""The reports stand on the result contract alone: importing them loads neither the engine nor
the drafter."""

import subprocess
import sys

PROBE = (
    "import sys, aiact.report; "
    "print(sorted(m for m in sys.modules "
    "if m.split('.')[:2] in (['aiact', 'engine'], ['aiact', 'drafting'])))"
)


def test_importing_the_reports_loads_neither_the_engine_nor_the_drafter() -> None:
    probe = subprocess.run(
        [sys.executable, "-c", PROBE], capture_output=True, text=True, check=True
    )
    assert probe.stdout.strip() == "[]"
