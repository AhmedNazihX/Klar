# Label changes

Every change to a label under `eval/cases/` is logged here: date, case id, old label → new label,
reason, and who approved it. After tag `labels-v1` (B10) a CI check requires an entry for every
changed case file.

For the academic set, the changes are applied by `aiact evaluate academic-import` from
`eval/cases/academic_overrides.yaml`; the source labels are the authors' (see
`eval/cases/academic/SOURCE.md`).

| Date | Case id | Old → new | Reason | Approved by |
| --- | --- | --- | --- | --- |
| 2026-09-28 | academic-0005 | prohibited (decided) → prohibited, `legally_ambiguous` | Art. 5(1)(a) needs significant harm, which the description can't settle | the user (B12 spot-check) |
| 2026-09-28 | academic-0136 | high_risk (decided) → high_risk, `legally_ambiguous` | Annex III 5(a) needs a public authority; the description doesn't say whether the pension scheme is public or private | the user (B12 spot-check) |
| 2026-09-28 | academic-0150 | high_risk (decided) → high_risk, `legally_ambiguous` | Annex III 3(a)/(c): the description doesn't say whether the scholarship decides admission or funds students already admitted | the user (B12 spot-check) |
| 2026-09-28 | academic-0116 | high_risk → high_risk (unchanged), note and citation `annex:III:7:b` added | Annex III 7(b) applies only when used by or on behalf of competent public authorities | the user (B12 spot-check) |
| 2026-09-28 | academic-0160, 0253, 0308, 0314, 0324, 0327 | low label unchanged; tag `scoring:low-or-out-of-scope` added | Rule- or template-based: may not be an AI system under Art. 3(1), so `out_of_scope` also counts, with a disagreement review | the user (B12 spot-check, pattern 2) |
