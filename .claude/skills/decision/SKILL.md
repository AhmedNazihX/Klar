---
name: decision
description: Writes a decision record in docs/decisions/NNN-<slug>.md for the AI Act project — what was decided, the options measured, the numbers and the choice. Use whenever a story makes a choice (embedding model, engine model, split vs leave-one-out, judge threshold, licence finding, freshness check), or when the user says to record, log or document a decision.
argument-hint: "<short title>"
---

# Record a decision: $ARGUMENTS

1. **Number it.** List the existing records and take the next free three-digit number. The backlog
   reserves some numbers for specific stories: 001 example count (B2), 002 appliedAI licence (B11),
   003 embeddings (X1), 004 engine model (X2), 005 OpenRouter (X3), 006 judge (V4) and 007 freshness (W0).
   If this decision belongs to one of those stories, use its number. Otherwise take the next number after the highest one used.
   ```bash
   ls docs/decisions/ 2>/dev/null
   ```
2. **Gather the facts** from the conversation, the story's output files, and the `eval_runs` records
   if there are numbers. Every number in the record needs a source (a file, a run_id, a command). Never
   estimate or round a number the user will quote in the README.
3. **Write** `docs/decisions/NNN-<kebab-slug>.md`:

```markdown
# NNN · <Title>

- **Date:** YYYY-MM-DD
- **Story:** <ID> (docs/BACKLOG.md)
- **Status:** accepted | superseded by NNN | proposed (waiting for the user)

## Question
One or two sentences: what had to be decided and why it matters. Link the INIT section.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| … | … | … | run_id / file / command |

## Decision
The choice, in one sentence, and the rule that decided it (for example INIT's "switch if >10% broken").

## Consequences
- What changes: settings, defaults, which stories are affected.
- What would make us revisit it.
```

4. **Apply** any setting the decision changes (for example, the default model in `backend/aiact/settings.py`),
   but only if the story's DoD asks for it. If it doesn't, list the change under Consequences.
5. If the decision needs the user's judgement (a licence reading, a label question, a trade-off that no rule
   decides), set the status to `proposed` and ask the user before you call it accepted.
