# 031 · Drafted documents: the result is shape-checked, the Act's text comes from the corpus

- **Date:** 2026-10-08
- **Story:** P28, P9 (docs/BACKLOG.md); also affects P25, P21, P22
- **Status:** accepted (the user chose option A on 2026-10-08)

## Question
The document routes (`POST /documents/vendor-letter` in P28, `POST /documents/drafts` and `/documents/export` in
P9) draft from a `ClassificationResult` the browser posts. P3's security audit and P8a's hand-over say to draft "only
from a backend-validated result, never from a row the browser wrote". The routes only validate the result's shape.
So a result edited before posting, or imported from someone else's export file (`import_my_data` accepts any result
object up to 256 kB), can put arbitrary text into a DRAFT document, and all three automatic checks still pass,
because they compare the document with that same result. The question was what "backend-validated" means.

## Options
| Option | What it means | Result | Source |
| --- | --- | --- | --- |
| A. Shape-checked; the Act's text from the corpus | Keep contract validation of the posted result. Every quoted provision in a drafted document is looked up by provision id, law version and language, and never taken from the posted result. Facts and answers stay the user's own | Fake law text becomes impossible; fake facts stay possible, but only on the user's own DRAFT, which says "based only on the description provided". Small change inside P28's fix round | P28 security review (MEDIUM: a forged `art:5:1:f` quote passed all three checks, reproduced via an ASGI client); P9 security review (MEDIUM, same trust boundary) |
| B. Server-signed results | `/classify` signs each result (HMAC); the document routes refuse unsigned or altered ones; P6 stores the signature; import keeps it | Fake facts and fake law text both impossible; older exports can no longer draft. A new story touching classify, P6 storage, import, P28 and P9 | P9 worker's report; P28 security review fix direction |
| C. Shape-checked only | No change; correct the docstrings | Fake law text stays possible, with checks reporting "passed" | — |

Both reviewers rated the issue MEDIUM, not HIGH: only the row's owner (or the author of a file the user chose to
import) can plant the content, and the document goes back only to that user. The `.docx` export is editable anyway.

## Decision
Option A: a posted result is validated against the contract, and any provision text a document quotes comes from
the corpus, never from the posted result. The user's facts and answers are the user's own. The rule that decided it:
remove what misleads (law text presented as the Act) at the lowest cost; signing buys little while documents are
DRAFTs of the user's own description.

## Consequences
- P28 (fix round): re-derive the Art. 5(1) quote in the prohibited message from the corpus at the result's
  `law_version` and the letter's language, and refuse or replace a quote that doesn't match. The facts check stays a
  comparison with the result. Correct the docstrings that say "backend-validated".
- P9: any quoted requirement in a draft or export comes from the corpus or the template (P8b's skeleton quotes
  already do); no quote is taken from the posted result. Correct its docstrings the same way.
- P25 (PDF report), P21 and P22 (the result screens that open the letters) follow the same rule.
- Duty wording counts as law text (user, 2026-10-09, P25 review): a report prints each duty's formal wording,
  condition and label from the obligations table (`aiact.report.duties`), keyed by class, role, article and law
  version; a posted duty the table lacks is left out and counted, never printed or used to date a tool. The posted
  dates and Art. 111(2) markings of matched duties are the run's own and stay.
- "Backend-validated result" in older notes (P3 audit, P8a hand-over) now means "contract-validated, with the law
  text re-derived from the corpus", not "issued by the backend".
- Revisit if a public deployment (S3) needs results that can be shown to third parties as Klar's own: option B
  then becomes its own story.
