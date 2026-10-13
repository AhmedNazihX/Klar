# Judge validation (V4)

The judge (`backend/aiact/eval/judge.py`) answers four yes/no checks. Before it scores anything,
it is validated here against hand labels (INIT › Evaluation › Judge; decision 006).

| File | What it holds | Who writes it |
| --- | --- | --- |
| `cases.yaml` | 48 cases, 24 English and 24 German, 6 per check and language: a claim and the text it must rest on | V4 (drafted from the Act and invented descriptions) |
| `labels.yaml` | your label for each case: `yes` or `no` | **you** |
| `answers.jsonl` | both judges' answers per case: Jev's probability of yes, the backup judge's verdict and reason, the cost | `aiact evaluate judge-validation` |
| `report.md` | agreement with your labels, Jev's calibration, and the unsure-margin table | `aiact evaluate judge-validation` |

## How to label

Read each case in `cases.yaml` and write `yes` or `no` after its id in `labels.yaml`. Judge only
from the two texts in the case, not from what you know about the Act or the system beyond them.
Leave a case empty if you can't decide: it is then left out of every measure. `yes` always means
the check passes:

| Check | `claim` is … | `source` is … | Answer `yes` when … |
| --- | --- | --- | --- |
| `citation_support` | a sentence the assistant wrote | the provision it cited, quoted word for word | everything the claim states follows from the cited text; a different actor, condition, deadline or amount is `no` |
| `evidence_tag` | a fact the assistant tagged "stated" | the company's description | the description says the fact, in any words; a fact it only makes likely, leaves open or contradicts is `no` |
| `qa_support` | a question and the assistant's answer | the sources it cited | every statement in the answer follows from the sources |
| `invented_content` | a passage of a drafted document | the facts the user supplied | every fact in the passage comes from the supplied facts; general wording that states no fact is fine |

The judges read the same question and criteria (`CHECKS` in `judge.py`), so a label that follows
this table measures them on the same task.

## Running it

From `backend/`, after labelling (each run asks only the cases not yet answered by both judges,
and again any case whose texts or check wording changed):

```
uv run aiact evaluate judge-validation --dry-run      # plan and cost estimate, no call
uv run aiact evaluate judge-validation                # both judges, then report.md
uv run aiact evaluate judge-validation --report-only  # report.md again after changing labels
```

Labels can change after the run: `--report-only` recomputes the report for free. A run stops at
the first case whose backup call reaches no model (a blocked route or a wrong key): fix the route
and run again. The report recommends no margin while a labelled case has a failed judge.
