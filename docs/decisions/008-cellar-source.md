# 008 · Fetch the laws from the Publications Office Cellar, not EUR-Lex

- **Date:** 2026-09-27
- **Story:** B1 (docs/BACKLOG.md)
- **Status:** accepted

## Question
Where should `aiact corpus fetch` download the EUR-Lex texts from (the AI Act, the Omnibus 2026/1744
and the consolidated text 02024R1689-20260727, each in EN and DE)? The source has to give the same
bytes for the same document on every run, because B1's DoD requires that a matching sha256 means
nothing has changed (INIT › Legal corpus; corpus rule "ingestion is re-runnable and idempotent").

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| EUR-Lex HTML (`eur-lex.europa.eu/legal-content/<LANG>/TXT/HTML/?uri=CELEX:<n>`) | Access for a scripted client | After about 6 requests: HTTP 202, empty body, `x-amzn-waf-action: challenge`. A retry with 10/20/40 s backoff still ended in 202 for `ai-act-consolidated.de` | `curl -D -` on the Omnibus URL; second real run of `aiact corpus fetch` |
| EUR-Lex HTML | Stability of the bytes across two downloads | They differ on every download. EUR-Lex adds a tracking script (`ruxitagentjs…`, `lastModification=…`) to each response. `ai-act.en` was 1,264,455 bytes, then 1,264,456 bytes, with a different sha256 each time (`442beebf…` → `0f430745…`) | Two runs of `aiact corpus fetch`, diff of `data/manifest.yaml` |
| Cellar XHTML (`publications.europa.eu/resource/celex/<n>`, `Accept: application/xhtml+xml`, `Accept-Language: eng\|deu`) | Access and stability | No challenge. Two requests for each of 4 documents (Act and consolidated text, EN and DE) returned identical sha256 (e.g. Act EN `8f0b656302f9…`, 1,262,391 bytes). An unknown CELEX gives HTTP 404 | Probe script during B1; two real runs, `cmp` says the manifests are byte-identical |
| Cellar XHTML vs EUR-Lex | Is it the same document? | Visible text is word-for-word identical: AI Act EN 90,483 words, DE 82,405 words. Same CONVEX converter version and `generated_on` timestamp. Only the page chrome differs | Orchestrator's check during the B1 review |

## Decision
Download the laws as XHTML from Cellar by CELEX number, with `Accept-Language` choosing the language.
Record the EUR-Lex page as each entry's `source_page`. Two reasons decided it: EUR-Lex's bytes are
never stable, so the sha256 rule can't hold, and Cellar serves the same document. The user approved
this on the condition that it is the same document, and the orchestrator's check above confirms it.

## Consequences
- `aiact/corpus/sources.py`: laws have `url` set to the Cellar CELEX URL, plus `accept_language`
  (`eng`/`deu`) and `celex`. The manifest records all three, so a download can be repeated exactly.
- Cellar can serve a different language than the one asked for. So `aiact/corpus/fetch.py` accepts an
  HTML download only if its `<title>` names the requested language (`L_202401689DE…`,
  `Konsolidierter TEXT: … — DE — …`). If not, the download counts as failed (`available: null`).
- C1 parses the Cellar XHTML. It has the same structure as the EUR-Lex HTML, without EUR-Lex's
  scripts and page chrome.
- Guideline PDFs still come from the Commission (`ec.europa.eu/newsroom/dae/redirection/document/<n>`).
  Their language isn't checked at fetch time; C2 checks it after Docling extracts the text.
- Revisit this if Cellar starts blocking scripted clients, changes its content negotiation, or its
  text stops matching EUR-Lex.
