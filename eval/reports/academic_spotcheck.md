# Academic benchmark: label spot-check

**Status: reviewed by the user on 2026-09-28.** The user saw each case with the verbatim provision text.
The "Draft reading" lines are the agent's suggestions from before the review; the *User verdict* lines
are the decisions. The label changes are applied from `eval/cases/academic_overrides.yaml` and logged
in `eval/LABEL_CHANGES.md`.

## What is checked

The academic set (`eval/cases/academic/`, 339 cases, source and licence in `SOURCE.md`) keeps the
authors' labels. INIT › Test sets says they are spot-checked before use. For each of the 20 cases below,
the user checks:

1. **Risk class.** Is the source label right under the AI Act as amended by the Omnibus (2026/1744)?
2. **Role.** Is `provider` or `deployer` right for the description?
3. **Conversion.** Does the description read as the scenario did? (Each field is copied unchanged.)

Record *agree*, or *disagree* with the label you would give, and a short reason.

## How the sample was chosen

Five cases per risk class, drawn with a fixed seed by `spotcheck_sample` in
`backend/aiact/eval/academic.py` (seed `20260928`); `aiact evaluate academic-sample` prints the same 20 ids.
The set holds 70 prohibited, 86 high-risk, 84 limited and 99 minimal cases.

## A pattern to decide on first

The source's `limited` label doesn't seem to mean "has an Art. 50 transparency duty". Four of the five
sampled `limited` cases (a recommender, a forecaster, an energy tips tool, a habit coach) trigger none of
Art. 50(1)–(4), and the source's `minimal` cases include content generators that may trigger Art. 50(2).
If the user agrees, one option is to score `limited_risk` and `minimal_risk` as a single "low" bucket
for this set, the way the appliedAI `low` label is scored. That is a scoring choice for V2, not a label
change.

**Decided (user, 2026-09-28):**
- **Pattern 1:** for this set, `limited_risk` and `minimal_risk` count as one low bucket in risk-class
  accuracy (cases 0161, 0190, 0208, 0216). Other sets still score them exactly.
- **Pattern 2:** a rule- or template-based system may not be an AI system under Art. 3(1). The source's
  low label is kept, but `out_of_scope` also counts as correct, and each such answer is listed for the
  disagreement review, as with appliedAI `low` (cases 0160, 0253, 0308, 0314, 0324, 0327).
  **Extended (user, 2026-09-28, option (a)):** the tag `scoring:low-or-out-of-scope` is applied by rule
  to every decided `limited` or `minimal` case whose system type starts with "Rule-based" or
  "Template-based": 95 cases at the pinned source commit, the six reviewed ones included.

## Cases

### 1. academic-0005 · source: prohibited · provider

```
Role: Provider
System type: Subliminal visual cue engine
Intended use: Provide a video streaming service that inserts barely perceptible visual prompts to increase subscription upgrades
Input data: Video frames, user watch history, subscription status, demographic data
Domain: Entertainment
```

- Draft reading: agree, prohibited under Art. 5(1)(a) (subliminal techniques beyond a person's
  consciousness that distort behaviour).
- Doubt: Art. 5(1)(a) also needs "significant harm". Is being nudged into a subscription upgrade
  significant harm? If not, this is not prohibited.
- **User verdict:** [ ] agree [x] disagree → label: prohibited, `legally_ambiguous` · reason: the Art. 5(1)(a) significant-harm condition can't be settled from the description

### 2. academic-0013 · source: prohibited · provider

```
Role: Provider
System type: Disability exploitation marketing engine
Intended use: Provide a marketing AI that leverages disability‑related data to push high‑priced assistive devices to vulnerable users
Input data: Medical disability reports, purchase history, income data, location data
Domain: Assistive technology
```

- Draft reading: agree, prohibited under Art. 5(1)(b) (exploiting vulnerabilities due to disability).
- Doubt: again the significant-harm condition. The financial harm to vulnerable buyers seems plausible here.
- **User verdict:** [x] agree → prohibited · reason: Art. 5(1)(b); the harm is stated by the description

### 3. academic-0028 · source: prohibited · deployer

```
Role: Deployer
System type: Civic engagement scoring tool
Intended use: Run a transportation‑ticketing system that denies discounts to passengers with low civic engagement scores
Input data: Public transport usage, community event participation, social media activity, age
Domain: Transportation
```

- Draft reading: agree, prohibited under Art. 5(1)(c)(i) (a social score from community and social
  media behaviour, leading to worse treatment in an unrelated context, ticket prices).
- Doubt: none.
- **User verdict:** [x] agree → prohibited · reason: Art. 5(1)(c)(i)

### 4. academic-0036 · source: prohibited · deployer

```
Role: Deployer
System type: Leadership corruption risk scorer
Intended use: Run a community‑grant allocation system that denies funds to organisations whose leaders are flagged as high‑risk for corruption based on personality profiling
Input data: Public speeches, social media posts, psychometric data, financial disclosures
Domain: Non‑profit
```

- Draft reading: agree, prohibited under Art. 5(1)(d) (predicting the risk of a person committing a
  criminal offence based on personality traits), or else Art. 5(1)(c).
- Doubt: Art. 5(1)(d) needs the assessment to rest "solely" on profiling or personality traits; the
  financial disclosures may be objective facts. Also, the decision falls on organisations, not only on
  the leaders.
- **User verdict:** [x] agree → prohibited · reason: Art. 5(1)(d); the intended use names personality profiling as the basis

### 5. academic-0057 · source: prohibited · provider

```
Role: Provider
System type: Trade‑union membership inference engine
Intended use: Provide a consumer‑insights platform that groups shoppers by inferred trade‑union membership from facial cues for price discrimination
Input data: In‑store camera images, purchase logs, demographic data, loyalty card ID
Domain: Retail
```

- Draft reading: agree, prohibited under Art. 5(1)(g) (biometric categorisation inferring trade union
  membership).
- Doubt: none.
- **User verdict:** [x] agree → prohibited · reason: Art. 5(1)(g)

### 6. academic-0096 · source: high-risk · deployer

```
Role: Deployer
System type: Employee performance monitoring AI
Intended use: AI system that monitors employee productivity through webcam and keystroke analysis, influencing performance evaluations
Input data: Video feeds, keyboard/mouse activity, task completion timestamps
Domain: Employment, workers’ management and access to self‑employment
```

- Draft reading: agree, high-risk under Annex III 4(b) (monitoring and evaluating the performance and
  behaviour of workers).
- Doubt: if the webcam analysis read emotions, Art. 5(1)(f) (emotion recognition at work) would make it
  prohibited. The description doesn't say so.
- **User verdict:** [x] agree → high-risk · reason: Annex III 4(b); the engine must ask whether the webcam analysis infers emotions, which would make it prohibited under Art. 5(1)(f)

### 7. academic-0113 · source: high-risk · provider

```
Role: Provider
System type: Corporate recruitment AI
Intended use: AI platform that automates the evaluation of job applicants for a multinational corporation, including bias‑mitigation scoring
Input data: Resumes, online profiles, assessment results
Domain: Employment, workers’ management and access to self‑employment
```

- Draft reading: agree, high-risk under Annex III 4(a) (evaluating candidates).
- Doubt: none.
- **User verdict:** [x] agree → high-risk · reason: Annex III 4(a)

### 8. academic-0116 · source: high-risk · deployer

```
Role: Deployer
System type: Migration security profiling AI
Intended use: AI that profiles migrants based on travel routes and biometric data to assess security risk
Input data: Passport scans, travel itineraries, facial images
Domain: Migration, asylum and border‑control management
```

- Draft reading: agree, high-risk under Annex III 7(b) (assessing a security risk posed by a person
  entering a Member State).
- Doubt: Annex III 7 applies only when used by or for competent public authorities. The description
  implies this but doesn't say it.
- **User verdict:** [x] agree → high-risk · reason: Annex III 7(b); note added: it applies only when used by or on behalf of competent public authorities

### 9. academic-0136 · source: high-risk · deployer

```
Role: Deployer
System type: Pension eligibility AI
Intended use: AI that determines eligibility for pension benefits based on contribution history and age
Input data: Contribution records, employment history, demographic data
Domain: Access to and enjoyment of essential private services and essential public services and benefits
```

- Draft reading: agree, high-risk under Annex III 5(a) (eligibility for public assistance benefits),
  if a public authority uses it.
- Doubt: (1) nothing says the deployer is a public authority; a private pension fund isn't covered by
  5(a). (2) Eligibility from contribution history and age may be a fixed rule, which isn't an AI system
  under Art. 3(1) (then `out_of_scope`).
- **User verdict:** [ ] agree [x] disagree → label: high-risk, `legally_ambiguous` · reason: Annex III 5(a) needs a public authority; follow-up question: is the pension scheme public or private?

### 10. academic-0150 · source: high-risk · deployer

```
Role: Deployer
System type: Doctoral scholarship allocation AI
Intended use: AI that evaluates the suitability of candidates for doctoral scholarships based on research output and academic record
Input data: Publications, citation counts, grades, demographic data
Domain: Education and vocational training
```

- Draft reading: unsure. Annex III 3(a) covers access or admission to education institutions; a
  scholarship is funding, not admission.
- Doubt: high-risk only if the scholarship decides admission to the doctoral programme. Otherwise no
  Annex III point clearly fits (possibly `minimal_risk`, or `legally_ambiguous`).
- **User verdict:** [ ] agree [x] disagree → label: high-risk, `legally_ambiguous` · reason: Annex III 3(a)/(c); follow-up question: does the scholarship decide admission, or fund students already admitted?

### 11. academic-0160 · source: limited · deployer

```
Role: Deployer
System type: Rule‑based optimizer using consumption patterns
Intended use: AI‑driven energy‑consumption advisory for residential users, offering tips to reduce bills
Input data: Anonymised household electricity usage statistics, public weather data
Domain: Energy
```

- Draft reading: disagree, `minimal_risk`. No Art. 50 duty applies (not a chatbot, no generated
  content, no emotion recognition).
- Doubt: "rule-based" may mean it isn't an AI system under Art. 3(1) (then `out_of_scope`).
- **User verdict:** [x] agree (low) · reason: rule- or template-based: the source's low label is kept, and `out_of_scope` also counts as correct and goes to the disagreement review (pattern 2; tag `scoring:low-or-out-of-scope`)

### 12. academic-0161 · source: limited · provider

```
Role: Provider
System type: Time‑series forecasting model
Intended use: Tool that forecasts agricultural yield for small farms to aid planning, not used for insurance underwriting
Input data: Open satellite imagery, weather forecasts, anonymised farm production records
Domain: Agriculture
```

- Draft reading: disagree, `minimal_risk`. No Annex III point and no Art. 50 duty.
- Doubt: none.
- **User verdict:** [x] agree (low) · reason: no Annex III point and no Art. 50 duty; limited_risk and minimal_risk scored as one low bucket for this set (pattern 1)

### 13. academic-0190 · source: limited · deployer

```
Role: Deployer
System type: Collaborative filtering engine
Intended use: AI‑driven personal reading recommender for e‑book platforms
Input data: Public book metadata, anonymised reading histories
Domain: Publishing
```

- Draft reading: disagree, `minimal_risk`. A recommender has no Art. 50 duty.
- Doubt: none.
- **User verdict:** [x] agree (low) · reason: limited_risk and minimal_risk scored as one low bucket for this set (pattern 1)

### 14. academic-0208 · source: limited · deployer

```
Role: Deployer
System type: Recommendation engine
Intended use: AI‑driven virtual career mentor that suggests skill‑development pathways
Input data: Public occupational standards, anonymised user skill profiles
Domain: Career Services
```

- Draft reading: unsure. `limited_risk` under Art. 50(1) only if the "virtual mentor" talks with users
  directly; as a recommendation engine it is `minimal_risk`.
- Doubt: Art. 50(1) is a provider duty; the role here is deployer.
- **User verdict:** [x] agree (low) · reason: limited_risk and minimal_risk scored as one low bucket for this set (pattern 1)

### 15. academic-0216 · source: limited · deployer

```
Role: Deployer
System type: Recommendation engine
Intended use: AI‑based personal habit‑formation coach that suggests incremental changes
Input data: Anonymised habit logs, public behaviour change research
Domain: Consumer Technology
```

- Draft reading: disagree, `minimal_risk`, for the same reason as case 14; "coach" doesn't say it
  interacts directly with users.
- Doubt: same as case 14.
- **User verdict:** [x] agree (low) · reason: limited_risk and minimal_risk scored as one low bucket for this set (pattern 1)

### 16. academic-0253 · source: minimal · deployer

```
Role: Deployer
System type: Rule‑based financial advisor
Intended use: AI that offers basic budgeting tips based on user‑entered expense categories
Input data: User expense categories, public budgeting guidelines
Domain: Personal finance
```

- Draft reading: agree, `minimal_risk`.
- Doubt: "rule-based" may mean it isn't an AI system under Art. 3(1) (then `out_of_scope`).
- **User verdict:** [x] agree (low) · reason: rule- or template-based: the source's low label is kept, and `out_of_scope` also counts as correct and goes to the disagreement review (pattern 2; tag `scoring:low-or-out-of-scope`)

### 17. academic-0308 · source: minimal · provider

```
Role: Provider
System type: Template‑based mood‑board generator
Intended use: AI that creates simple visual mood boards from user‑provided colour palettes
Input data: User colour palette, public image assets
Domain: Design
```

- Draft reading: agree, `minimal_risk`, if the boards are assembled from existing assets.
- Doubt: if it generates synthetic images, Art. 50(2) (marking generated content) makes it
  `limited_risk`. "Template-based" suggests it doesn't.
- **User verdict:** [x] agree (low) · reason: rule- or template-based: the source's low label is kept, and `out_of_scope` also counts as correct and goes to the disagreement review (pattern 2; tag `scoring:low-or-out-of-scope`)

### 18. academic-0314 · source: minimal · provider

```
Role: Provider
System type: Template‑based description generator
Intended use: AI that generates short product description snippets from user‑provided feature list
Input data: User feature list, public marketing copy
Domain: E‑commerce
```

- Draft reading: unsure. A provider of an AI system that generates synthetic text has the Art. 50(2)
  marking duty, which would make it `limited_risk`.
- Doubt: if it only fills templates, it isn't generating synthetic content (or isn't an AI system at all).
- **User verdict:** [x] agree (low) · reason: rule- or template-based: the source's low label is kept, and `out_of_scope` also counts as correct and goes to the disagreement review (pattern 2; tag `scoring:low-or-out-of-scope`)

### 19. academic-0324 · source: minimal · provider

```
Role: Provider
System type: Template‑based card generator
Intended use: AI that creates basic greeting card designs from user‑provided occasion and message
Input data: User occasion and message, public design assets
Domain: Personalisation
```

- Draft reading: agree, `minimal_risk`, for the same reason as case 17.
- Doubt: same as case 17 (Art. 50(2) if it generates images).
- **User verdict:** [x] agree (low) · reason: rule- or template-based: the source's low label is kept, and `out_of_scope` also counts as correct and goes to the disagreement review (pattern 2; tag `scoring:low-or-out-of-scope`)

### 20. academic-0327 · source: minimal · deployer

```
Role: Deployer
System type: Rule‑based advice system
Intended use: AI that offers basic pet grooming tips based on pet type entered by the user
Input data: User pet type, public grooming guidelines
Domain: Pet care
```

- Draft reading: agree, `minimal_risk`.
- Doubt: "rule-based" may mean it isn't an AI system under Art. 3(1) (then `out_of_scope`).
- **User verdict:** [x] agree (low) · reason: rule- or template-based: the source's low label is kept, and `out_of_scope` also counts as correct and goes to the disagreement review (pattern 2; tag `scoring:low-or-out-of-scope`)

## Result

| | Count |
| --- | --- |
| Cases checked | 20 |
| Agree | 17: 8 as labelled (0161 also falls under pattern 1), 3 more under pattern 1 (0190, 0208, 0216), 6 under pattern 2 |
| Disagree (→ `legally_ambiguous`) | 3 (0005, 0136, 0150) |
| Roles wrong | 0 |
| Conversion problems | 0 |

- Decision on the `limited` / `minimal` pattern: pattern 1 and pattern 2 above.
- How the set is used from here: with corrected labels. The three `legally_ambiguous` changes and the
  0116 note are overrides applied at import; pattern 1 is a scoring rule for this set; pattern 2 is a
  tag plus a scoring rule with a disagreement review. Results on this set are reported separately.
- Reviewed by: the user · date: 2026-09-28
