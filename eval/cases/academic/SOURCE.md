# Academic benchmark: source and attribution

The cases in this folder are converted from the **AI Act Evaluation Benchmark** by Athanasios Davvetas,
Michael Papademas, Xenia Ziouvelou and Vangelis Karkaletsis:

- Repository: <https://github.com/davidath/ai-act-evaluation-benchmark>, file `scenarios.json`,
  commit `d323167f5597dfd9365b376c9afe7b0e414eb81a` (26 June 2026),
  sha256 `0fc1c7491372cf0aa787b4b650f77245ec775f8bff0c4c84f253435c7dcb1b25`.
- Paper: A. Davvetas, M. Papademas, X. Ziouvelou, V. Karkaletsis, *AI Act Evaluation Benchmark: An Open,
  Transparent, and Reproducible Evaluation Dataset for NLP and RAG Systems*, arXiv:2603.09435, 2026.
- Licence: the JSON data is licensed under
  [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
  The repository's scripts are Apache 2.0; none of them is used here.

## Changes made

`aiact evaluate academic-import <path to scenarios.json>` (code in `backend/aiact/eval/academic.py`) made these
changes, and no others:

- Each scenario's `role`, `system_type`, `intended_use`, `input_data` and `domain` are joined, one labelled
  line each, into the case `description`. Their wording is unchanged.
- `risk_level` is mapped onto this project's classes: `prohibited` → `prohibited`, `high-risk` →
  `high_risk`, `limited` → `limited_risk`, `minimal` → `minimal_risk`. `role` is mapped to `provider` or
  `deployer`.
- Case ids are `academic-NNNN`, the 1-based position in the source's `data` list; the 0-based position
  is also kept as the tag `source:scenarios.json:data:<n>`.
- `related_articles` are kept as `related:art:<n>` tags (sorted, duplicates dropped). They are not used
  as `label_citation`, because the source generated them as related articles, not as the provisions
  that settle the label.
- The generated `obligations` are left out: this set checks the risk class and the role only.
- The cases are grouped into one file per risk class.

The labels are the authors', not this project's. They are spot-checked in
`eval/reports/academic_spotcheck.md`, and results on this set are reported separately (INIT › Test sets).
