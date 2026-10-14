# appliedAI benchmark: source and attribution

The files in this folder come from the **Risk Classification Database** of the
**appliedAI Institute for Europe gGmbH**. Credit: "appliedAI Institute for Europe gGmbH".

- Licence: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
  Slide 16 of the deck states it ("can be freely shared, adapted and used for commercial purposes if it is
  correctly credited to 'appliedAI Institute for Europe gGmbH'"), and the Notion page says "Licence: CC BY 4.0".
- Retrieved 2026-10-14. Decision 002 (`docs/decisions/002-appliedai-licence.md`) records the fields, the
  languages and the licence finding.

## Files

| File | What it is | Where it came from | sha256 |
| --- | --- | --- | --- |
| `source/appliedai-risk-classification-database-2024-09.pdf` | The deck (24 Sep 2024, 17 slides): fields, statistics, limitations, licence. It holds no cases | <https://www.appliedai-institute.de/en/resources/risk-classification-database/> | `af990309211ce897e9e002201b2c2f744fd1b7d920bf2ff32f23e903f4f248c5` |
| `source/appliedai-use-case-database.json` | The "Use Case Database": the 106 AI systems appliedAI classified itself (batch #1 in the deck), every field as published, sorted by `ID`; `_block` is the Notion row id | The Notion page <https://appliedaiinitiative.notion.site/2b58830bb7f54c9d8c869d37bdb27709>, collection `16c16466-adad-4cb4-9e94-ca9ea6bcbce3`, read through Notion's public page API | `5e291296b81ac2406036ac5cc3d6b38346fe21f581eb9cc418dec9c576a9eee0` |
| `source/appliedai-use-case-database.csv` | The same rows and fields as the JSON, for a spreadsheet | converted from the JSON | `7b0f3d031c5de46813f2d312d8fc58f36255605da164ebff56f958cdb0823f44` |

The institute's current website lists 641 systems: these 106 plus 535 classified by the University of
Kaiserslautern (Hauer et al., 2023). The 535 are not used here; the website shows no case IDs or Annex fields.

## Changes made: `appliedai.jsonl`

`appliedai.jsonl` (106 lines, the file `APPLIEDAI_FILE` loads) was made once from the JSON on 2026-10-14
(B11), with these changes and no others:

- One case per system, sorted by appliedAI's `ID`; the case id is `aai-NNN`, NNN that ID (1–119, with gaps).
- `description` is `Details, DE`, the original German (the user's choice; the English is machine translated).
  Runs of spaces and line breaks become one space, blank lines stay paragraph breaks; the wording is unchanged.
- `label` is the experts' own label, mapped only in spelling: `high-risk` → `high`, `low-risk` → `low`,
  `It is unclear` → `unclear`, `prohibited` → `prohibited`. `score_appliedai` maps it at scoring time.
- `notes` is the experts' `Comment` with its spaces tidied the same way; 30 systems have none (an empty or
  non-breaking-space cell).
- `tags`:
  - `source:appliedai:id:<ID>`;
  - `annex_i` where the source says "Annex II" (today's Annex I; reported separately), `annex_iii` where it
    says "Annex III";
  - `annex_iii:<item>` from `Item in Annex III` (aai-093, the prohibited case, has item 1 but no Annex field);
  - `prohibited_unclear` where `AI prohibited` is "It is unclear";
  - `function:<slug>`, appliedAI's own `Enterprise Function, EN` (for example `function:human_resource_management`).
- Left out: the titles, `Details, EN`, `Enterprise Function, DE`, `Subitem in Annex III`, `Sources` and
  `Files & media`. They stay in the JSON.

## Limits the source states

The systems were classified in 2023 against the Commission's 2021 proposal: there is no Art. 6(3) filter,
"Annex II" means today's Annex I, and "Art. 52" today's Art. 50. The English texts were partly machine
translated. See slide 14 of the deck.
