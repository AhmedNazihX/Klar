# 028 · The leak check ignores runs that are the Act's own wording

- **Date:** 2026-10-02
- **Story:** E4 (docs/BACKLOG.md); amends decision 015
- **Status:** accepted (user, 2026-10-02, option B)

## Question
Decision 015 forbids any 5-word run shared between an engine prompt and a Pile B row. E4's isolation audit found two
follow-up questions in `backend/aiact/engine/nodes/prohibited_texts.py` that quote Art. 5 word for word and still
fail, because the Pile B examples quote the same words:

| Run | Act wording | Matches |
| --- | --- | --- |
| "from the internet or cctv" | Art. 5(1)(e), "untargeted scraping of facial images from the internet or CCTV footage" | hr-ex-019 |
| "based on their biometric data" | Art. 5(1)(g), "categorise individually natural persons based on their biometric data" | hr-ex-047 |

The prohibited node always puts the full text of Art. 5 into the prompt (E4 DoD: "always fetches Art. 5"), so
rewording a question line does not keep these words from the model. The question was whether to keep the rule
strict and reword, or to stop counting the Act's own wording as a leak.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| A. Reword every question that quotes the Act | Leak-protection gain | None: the same words reach the model through the Art. 5 text in the prompt | E4 isolation audit, 2026-10-02; `prohibited_retrieval.py` |
| **B. Exempt runs that also appear in the Act's text** | Pile B 5-word runs that also occur in `data/parsed/{ai-act,ai-act-consolidated,omnibus}.en.jsonl` | 277 of 11,013 (2.5%), spread over 77 of the 153 Pile B rows | The command below with `I=B.keys()&A` printed, at data commit f4e38b9 |
| B, applied to E4 | Amended check on the branch's `prompts/prohibited.md`, `nodes/prohibited_texts.py` and E2's `prompts/facts.md` | "no shared 5-word runs outside the Act text" for all three | The command below, 2026-10-02 |

## Decision
Option B. A 5-word run that also appears in the AI Act's own text (the original Act, the consolidated text or the
Omnibus amending regulation, English parsed files under `data/parsed/`) is not counted by the leak check. Guidance
documents (`guide-*`, `code-of-practice-*`) are never exempt: they contain the Commission examples themselves.

Decision 015's other half stands: a prompt must never **paraphrase** a Pile B example's deciding feature, and the
isolation audit still judges that by reading, whether or not the words are statutory. E4's "by comparing their
biometric data … with a reference database" passes the amended check (Art. 3(36) uses the run), but it sits close
to hr-ex-014's deciding sentence, so it is still reworded to Art. 3(41)'s definition.

Amended leak check (pass the prompt file; prints each shared run with the example it matches):

```bash
uv run --project backend python -c 'import json,re,sys
W=lambda t:re.findall(r"[a-z0-9]+",re.sub("[’\x27]","",t.lower()))
G=lambda w:{tuple(w[i:i+5]) for i in range(len(w)-4)}
pb=set(json.load(open("eval/split.json"))["pile_b"])
rows=[r for r in map(json.loads,open("eval/commission_examples/examples.jsonl")) if r["example_id"] in pb]
B={g:r["example_id"] for r in rows for t in (r["text"],r["lead_in"] or "",r["use_case"] or "",json.dumps(r["flip_variants"])) for g in G(W(t))}
A={g for f in ("ai-act","ai-act-consolidated","omnibus") for r in map(json.loads,open(f"data/parsed/{f}.en.jsonl")) for g in G(W(r["text"]))}
P=G(W(open(sys.argv[1]).read()))
print(len(rows),"Pile B rows;",sorted((" ".join(g),B[g]) for g in (P&B.keys())-A) or "no shared 5-word runs outside the Act text")' <prompt file>
```

## Consequences
- The isolation audit runs this command, not decision 015's, on every changed prompt file and on the question and
  prompt texts in engine node modules (`*_texts.py`), from E4 on. The check stays in the audit (it reads denied
  files, so Engine-lane workers can't run it).
- E4 keeps its Art. 5(1)(e) and 5(1)(g) wording in `prohibited_texts.py`, and rewords the `real_time_identification`
  line in `prompts/prohibited.md` to Art. 3(41).
- E6 (Art. 50) and E8 may quote the Act's terms ("emotion recognition system", "deep fake") in prompts and questions.
- The German parsed texts are not in the exemption: the check works on English text only, as before.
- **Revisit** if the audit finds a Pile B deciding feature that is itself pure Act wording and decisive for that
  example's verdict, or if a new Act text (another amending regulation) is added under `data/`.
