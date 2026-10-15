# 037 · Retrieval is code: the engine looks things up before each model call, and the model gets no tools

- **Date:** 2026-10-15 (retroactive: it records how the engine has worked since E1, E4 and E5)
- **Story:** W2 (docs/BACKLOG.md); the user's answer to the orchestrator's open offer of 2026-10-12
- **Status:** accepted 2026-10-15, retroactive

## Question
INIT › How it works said that "inside each step the model decides what to look up", which reads as a tool-using
agent. The engine was built otherwise: decision 004 (lines 86-87) already notes that "the nodes make no tool
calls: retrieval is code, so structured output is the models' only interface". No record said so as a decision.

## Options
| Option | What it means | Chosen |
| --- | --- | --- |
| A. Retrieval in code | Each node's code fetches and searches the corpus before the model call; the model reads what it is given and answers in a fixed JSON schema | **A** |
| B. Retrieval as tools | The model gets `get_provision` and `search_ai_act` as tools and decides what to look up inside each step | — |

## Decision
The engine retrieves in code, before each model call, and the model gets no tools.

- **Law text with a fixed address is looked up whole:** Art. 5 for the prohibited check, Art. 50 for transparency
  (`engine/nodes/guideline_retrieval.py`), and every Annex III point and every Annex I point for the high-risk
  check (`engine/nodes/high_risk_retrieval.py`).
- **Guideline passages are searched** with the description, for reasoning by analogy (the same two files), with
  the held-out examples filtered out (decision 012).

## Why
- **The law gives the address.** A softly worded description must not miss its Annex point because a search
  ranked it low (user, 2026-09-30, quoted in `high_risk_retrieval.py`'s docstring); fetching the whole article or
  annex means the model reads every point and condition.
- **No check can be skipped.** The graph's edges are fixed and a node only returns its outcome
  (`engine/graph.py`), so every run takes the Act's order: facts → scope → prohibited → high_risk → transparency →
  role_obligations → finalize.
- **Reproducible and testable.** What the model sees is decided by code, so it can be asserted in tests and
  replayed from recordings.

## Consequences
- **Trade-off:** no free exploration. The model can't follow a cross-reference the code didn't fetch. Story S1
  (stretch: fixed order vs free agent) would measure what that costs.
- INIT › How it works is corrected to match, citing this record.

## Sources
- Decision 004, lines 86-87.
- `backend/aiact/engine/graph.py`, `backend/aiact/engine/nodes/guideline_retrieval.py`,
  `backend/aiact/engine/nodes/high_risk_retrieval.py` (module docstrings).
