# Label changes

Every change to a label under `eval/cases/` is logged here: date, case id, old label → new label,
reason, and who approved it.

Since B10a (decision 017) CI enforces it with `aiact evaluate label-freeze --base <ref>` (the
rules are in `backend/aiact/eval/label_freeze.py`):

- A case is approved once a case file on main holds it; new cases need no row.
- An approved case whose record changes in any field (label, citation, description, notes, tags),
  or which is removed, needs a row added in the same branch. Overrides in
  `eval/cases/academic_overrides.yaml` count the same way, under the case id they override.
- The "Case id" cell names cases by id (`academic-0160, 0253` reuses the prefix for bare
  numbers), or by rule as "<N> <prefix> cases (by rule: …)".
- A rule row covers the changed cases with that id prefix that no id row names, and only when N
  equals their number exactly; several rule rows for one prefix are summed first. It never covers
  a label change (a case's `label`, `label_citation` or `as_of`, an override's `status`,
  `risk_class` or `label_citation`) or a removal: those always need an id row. So N counts the rule's cases
  minus any an id row already names.
- Rows are only ever added: editing or deleting an existing row fails the check (re-aligning the
  columns doesn't). A mistake in an old row is fixed with a new, corrective row.

For the academic set, the changes are applied by `aiact evaluate academic-import` from
`eval/cases/academic_overrides.yaml`; the source labels are the authors' (see
`eval/cases/academic/SOURCE.md`).

| Date | Case id | Old → new | Reason | Approved by |
| --- | --- | --- | --- | --- |
| 2026-09-28 | academic-0005 | prohibited (decided) → prohibited, `legally_ambiguous` | Art. 5(1)(a) needs significant harm, which the description can't settle | the user (B12 spot-check) |
| 2026-09-28 | academic-0136 | high_risk (decided) → high_risk, `legally_ambiguous` | Annex III 5(a) needs a public authority; the description doesn't say whether the pension scheme is public or private | the user (B12 spot-check) |
| 2026-09-28 | academic-0150 | high_risk (decided) → high_risk, `legally_ambiguous` | Annex III 3(a)/(c): the description doesn't say whether the scholarship decides admission or funds students already admitted | the user (B12 spot-check) |
| 2026-09-28 | academic-0116 | high_risk → high_risk (unchanged), note and citation `annex:III:7:b` added | Annex III 7(b) applies only when used by or on behalf of competent public authorities | the user (B12 spot-check) |
| 2026-09-28 | academic-0160, 0253, 0308, 0314, 0324, 0327 | low label unchanged; note added | Rule- or template-based: may not be an AI system under Art. 3(1), so `out_of_scope` also counts, with a disagreement review | the user (B12 spot-check, pattern 2) |
| 2026-09-28 | 95 academic cases (by rule: decided `limited`/`minimal` source label, system type starting "Rule-based" or "Template-based") | low label unchanged; tag `scoring:low-or-out-of-scope` added | Pattern 2 extended to the whole set (option (a)): such systems may not be AI systems under Art. 3(1), so `out_of_scope` also counts, with a disagreement review | the user, 2026-09-28 |
| 2026-09-30 | own-b-09-voice-mood-prototype | out_of_scope (decided, Art. 2(8)) → high_risk, provider, `annex:III:1:c` | The user's planned-system rule: Art. 2(8) is a note, and a system being built is classified as the planned system; launch changed to "frühestens Anfang 2028" | the user (E3) |
| 2026-10-06 | own-a-11-email-tone-rewrite | limited_risk, `legally_ambiguous` → limited_risk (decided), provider, `obligation:art:50:2` unchanged | Guide paras 90-91 treat a change that affects meaning, style or intent as going beyond standard editing, and para 92's exception list covers only minor stylistic polishing that does not change the substance, meaning, style or messaging of text; a tone rewrite changes the style, so it is a substantial alteration and Art. 50(2) applies. Para 92's marking example (rewriting that changes style, structure and meaning) doesn't narrow that. | the user, 2026-10-06 (E6) |
