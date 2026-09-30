<!-- Copied from the Klar design system, https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4 (version 1790766074-7ac5, 2026-09-30). The artifact is the source: when it changes, re-copy this file. -->

# Components

Guidelines for each component of the design system. Props are in `components.d.ts`. The system's own React 18 bundle is a reference: the app builds these in `frontend/src/components/` with Tailwind and React 19.

## Button

The action control: one liquid Lens blue primary button per view, glass ghost buttons for everything else.

**Use primary** for the single next step the screen exists for: *Classify a tool*, *Add answers and run again*, *Draft documents*. A second primary on the same view means one of them is not the main step.

**Use ghost** for secondary actions beside it (*Edit description*, *Save draft*, *Download PDF*) and for small actions inside cards (*Change*).

Sizes: `md` (44 px) in the app, `lg` (52 px) on the landing page, `sm` (34 px) inside fact cards and rows.

The consumer provides the label, in sentence case, as a verb and its object. No arrows or chevrons in labels. Buttons never shrink in a row (`flex-shrink: 0`); when space runs out, the text beside them wraps.

## GlassPanel

The surface everything sits on: frosted glass over the mist-and-mesh ground.

- `glass` for cards and panels: fill `glass-top` to `glass-bottom` at 150°, 1 px `glass-rim`, `blur-glass` with `saturate-glass`, `shadow-glass`.
- `thin` for chips, inner cards and tracks inside a glass panel.
- `dark` only for code examples and dark showcase tiles; text on it is `paper`.

Glass needs something to blur: put it on the mist ground with mesh lights (`mesh-blue`, `mesh-peach`, `mesh-teal`, `mesh-lilac`), never on a flat white page. Body text never sits on anything thinner than `thin`. Radius follows size: `card` (28 px) by default, `panel` (32 px) for the sidebar and the result card, `feature` (36 px) for landing panels.

## RiskPill

The risk class of a tool: a coloured dot and the class name, always both, never colour alone.

| Class | Tokens |
|---|---|
| Prohibited | `risk-prohibited`, `-dot`, `-tint` |
| High-risk | `risk-high`, `-dot`, `-tint` |
| Limited risk | `risk-limited`, `-dot`, `-tint` |
| Minimal risk | `risk-minimal`, `-dot`, `-tint` |
| Out of scope | `risk-out`, `-dot`, `-tint` |

Set `assumed` while a status is open (*High-risk, assumed*): Klar works from the stricter reading until the question is answered or a lawyer has looked. The consumer passes the translated label as children in German (*Hochrisiko*). These colours belong to results only: never use them for brand, decoration or buttons.

## StatusPill

How settled a result is. It sits next to a RiskPill; it never replaces one.

- `decided`: the checks reached an answer on the facts given.
- `needs-info`: a fact that decides the outcome is missing. Dashed, because something is still to be filled in. Pair it with the question.
- `ambiguous`: the facts are clear but the law doesn't settle it. Show both readings and recommend a legal review.
- `draft`: the stamp on every drafted document.

No confidence percentages anywhere: they would imply a calibration Klar doesn't have.

## EvidenceTag

Where a fact came from, so a reader can challenge it: filled dot for *Stated* (the user said it), half dot for *Inferred* (Klar worked it out), ring for *Assumed* (a default the user must confirm).

The glyph carries the meaning, not colour, so the three tags stay neutral and never compete with risk colours. Every fact a step rests on carries one. *Assumed* facts always come with Confirm and Change actions (see FactCard).

## Icon

The Klar line icons: 24 px grid, 1.8 px stroke (2.2 to 2.8 for the small check, plus and send marks), round caps and joins, drawn in `currentColor`.

Icons label, they don't decorate: every nav item has one, buttons rarely do (*Add a tool* is the exception). Decorative icons are `aria-hidden`; give `title` only when an icon stands alone and carries meaning. The same drawings are in the Icons asset group as SVG files in ink.

## SegmentedControl

A pill-shaped switch between two or three equal views of the same thing: the law version, the language, Summary or Reviewer.

Every app screen carries the law-version control top right (*As amended, 27 Jul 2026* / *Original, 2024*); the language control sits at the foot of the sidebar.

The consumer provides `label` (the group's accessible name) and the options. Keep option labels short; in German they grow by about 30%. Use it for views, not for answers to questions: those are a set of buttons with `aria-pressed` in a fact prompt.

## SidebarNav

The app's main navigation, in the glass sidebar (248 px wide, 24 px from the page edges): Inventory, Classify a tool, Obligations, Documents, Ask about the Act.

The active item is white glass with `shadow-item-active` and `aria-current="page"`. Labels must fit 220 px at 15 px: in German pick short labels (*Fragen stellen*, not *Fragen zur KI-Verordnung*). The consumer provides the items; the logo, company card, language control and the AI notice sit around it in the sidebar.

## Citation

A provision quoted word for word, in Newsreader: the Act speaks in the serif, the product in Geist.

Quote the exact official text in the reader's language and name the source under it: article, paragraph, regulation and language (*Art. 6(3), last subparagraph, English*). Shorten only with an ellipsis, never paraphrase inside quotation marks. In German, take the wording from the official German text on EUR-Lex; the model never translates legal text itself.

## FactCard

One fact a result rests on, with its evidence tag; assumed facts get *Change* and *Confirm*.

Show the deciding facts beside every result under a heading like *The result rests on*, with the line *If any of these is wrong, the class may change.* Assumed cards get a Lens blue ring so they are found first. The consumer handles the actions: confirming updates the evidence to *Stated*; changing reopens the description and reruns the checks.

## StepRow

One step of the classification, collapsed: its name, a one-line decision and the provision it rests on.

The summary view lists every step in the Act's order (Facts, Role, 1 Scope, 2 Prohibited, 3 High-risk, 4 Transparency, Duties); expanding a row, or the Reviewer view, shows its StepCard. Columns are 180 / flexible / 200 px in English; pass `columns` as `220px minmax(0,1fr) 280px 20px` for German citations such as *Anhang III Nr. 4 Buchst. a, Art. 6 Abs. 3*. A citation never truncates or breaks mid-reference.

## StepCard

One step of the classification, expanded for a reviewer: the decision, the fact it rests on with its evidence tag, and the quoted provisions.

The step that decided a High-risk result gets `highlight` (an orange ring, `shadow-highlight-high`); all others stay plain glass. The outcome pill uses the same class and status pills as everywhere else. Put quotes side by side when there are two, stacked when there is one. The consumer provides every text; the component never writes legal content itself.

## CheckProgress

The live list of checks while Klar classifies a tool: done, running, waiting, always in the Act's order.

It sits beside the description while the checks run and announces changes politely (`aria-live`). The running step is lifted in white glass with a Lens blue ring and may show the closest matches it is comparing. Done steps show their outcome and article in one short line (*No match. Art. 5*). Never skip a step to look faster.

## ObligationItem

One duty on the to-do list: a checkbox, the duty in plain words, a link to its draft document if there is one, and the article.

Write the duty as an action the user takes (*Keep the logs it creates for at least six months*), not as the article's wording. The article sits right-aligned; its column is 86 px in English and at least 112 px in German (*Art. 26 Abs. 11*): pass `referenceWidth`. Wrap items in `<ul class="kl-obligations">`.

## FillMarker

A gap in a drafted document that only the user can fill: dashed Lens blue, never invented text.

Drafted documents contain only facts the user supplied or the classification established; everything else is a FillMarker that points to the guided interview (*To fill in. Answer in the interview on the right.*). Documents also carry the DRAFT StatusPill and the notice *Guidance, not legal advice.*

## Assets

### Logos

- **klar-lockup**: the primary logo, symbol and wordmark, on light grounds.
- **klar-lockup-on-dark**: the same with a `paper` wordmark, on `ink` or glass-dark.
- **klar-lockup-flat**: flat colours (`ink`, `lens-blue`, `logo-pale`) for print, Word and PDF.
- **klar-lockup-mono**: one ink, `#0F1B2D`, with white separators, for single-colour reproduction.
- **klar-symbol**: the bubble alone, for places the name is already written next to it.
- **klar-wordmark**: *Klar* alone, ink `#0F1B2D`, for tight horizontal spaces.
- **klar-app-icon**: the bubble on a glass tile, 1024 px.
- **klar-favicon**: the flat bubble for browser tabs; works down to 16 px.

Clear space: half the height of the capital K on every side. Minimum lockup height: 28 px.

### Icons

The Klar line set on a 24 px grid, round caps and joins, drawn in ink `#0F1B2D` in these files. In code use `Klar.Icon`, which draws the same paths in `currentColor`.

inventory, classify, obligations, documents, ask (sidebar navigation) · add (Add a tool) · privacy (personal-data notes) · check (done steps) · info (legal-review line) · alert (a step that needs attention) · chevron-down (expandable rows) · send (ask a question).
