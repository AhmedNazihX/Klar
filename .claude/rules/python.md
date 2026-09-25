---
paths:
  - "backend/**/*.py"
---

# Python rules (backend/)

**Tooling.** Python 3.12, managed by uv. `ruff format` formats the code (a hook runs it on every edit). `ruff check`
lints it, and sorts imports through ruff's `I` rules. `pyright` checks the types. Don't add black, isort or mypy.

**Types and data**
- Type-annotate every function signature. Avoid `Any`; use `object` or a precise type, and narrow it.
- Data that crosses a boundary is a **Pydantic v2 model**: engine results, API bodies, MCP tool outputs, benchmark
  cases, and anything written to or read from files. `aiact/schemas/` is the result contract; reuse it, never fork it.
  Use `ConfigDict(frozen=True)` for values that must not change. Plain `dataclass` is fine for purely internal holders.
- Prefer enums and literals from `aiact/schemas` (`RiskClass`, `Status`, `Role`, …) over raw strings.

**Configuration and secrets**
- Read settings only through `aiact.settings` (pydantic-settings). Never use `os.environ[...]` or `load_dotenv()` in modules.
- Never log, print or put into exceptions a key, a token, or a user's system description. Logs carry metadata only (INIT › Ethical considerations).
- Resolve data paths from the settings (`AIACT_DATA_DIR`), never from hard-coded paths.

**Structure** (see `docs/LAYOUT.md`)
- All code lives in `backend/aiact/`. Scripts are `aiact` CLI subcommands, not loose files.
- Model calls go only through `aiact.llm`. Retrieval code (`aiact.retrieval`) never calls an LLM.
- Keep functions small and single-purpose. Raise specific exceptions: no bare `except`, and never swallow an error just to continue.
- Use `logging`, not `print`. The CLI layer's own output is the only exception.
- Do blocking I/O outside async code paths, or use async clients. Never block the event loop in the API or the engine.

**Security**
- Pass parameters to SQL; never format them into the query string.
- `subprocess` gets argument lists, never `shell=True`.
- No `eval`, `exec` or `pickle` on anything that isn't ours.

**Tests** (pytest)
- Tests mirror the package: `backend/tests/<area>/test_<module>.py`. Shared inputs go in `tests/fixtures/`.
- No network in the default run. Model responses come from `tests/recordings/` (see `aiact.llm`). Mark real calls
  `@pytest.mark.live`; they're skipped unless you run `-m live`.
- Tests are deterministic: fixed seeds, no wall-clock sleeps, no dependence on the order they run in.
- Test behaviour through the public function. A test that can't fail for the bug it names isn't a test.
