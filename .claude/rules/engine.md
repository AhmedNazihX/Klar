---
paths:
  - "backend/aiact/engine/**"
---

# Rules for the engine

- This folder may exist only after `eval/split.json` is committed (a hook enforces this).
- The check order is fixed: facts → scope → prohibited → high_risk → transparency → role_obligations → finalize. No path may skip a check. Only `out_of_scope` and `prohibited` stop the run early.
- Every step returns its Pydantic `StepResult`, with citations and evidence tags. Every citation must resolve through `get_provision` (INIT: citation existence is a hard 100%).
- An uncertain outcome is a status (`needs_more_information` or `legally_ambiguous`), never a guess. `RiskClass` then holds the stricter reading as the labelled working assumption.
- Retrieval calls pass `exclude_source_example_ids` through from the caller (INIT › Benchmark isolation 2 and 4).
- Model calls go through `aiact/llm`. Tests use recorded responses, and live tests are marked `@pytest.mark.live`.
