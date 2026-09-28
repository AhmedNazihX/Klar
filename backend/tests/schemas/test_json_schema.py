"""Snapshot of the result contract's JSON Schema, so any change to it is deliberate.

After an intended change, regenerate with `AIACT_UPDATE_SNAPSHOTS=1 uv run pytest tests/schemas`.
"""

import json
import os
from pathlib import Path

from aiact.schemas import ClassificationResult

SNAPSHOT = Path(__file__).parent.parent / "snapshots" / "classification_result.schema.json"


def test_classification_result_json_schema_matches_snapshot() -> None:
    schema = ClassificationResult.model_json_schema()
    if os.environ.get("AIACT_UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    assert SNAPSHOT.exists(), f"missing snapshot {SNAPSHOT}; regenerate it (see module docstring)"
    assert schema == json.loads(SNAPSHOT.read_text())
