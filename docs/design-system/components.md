<!-- Copied from the Klar design system, https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4 (version 1790858064-dcaa, 2026-10-01). The artifact is the source: when it changes, re-copy this file. -->

# Components

Guidelines for each component of the design system. Props are in `components.d.ts`. The system's own React 18 bundle is a reference: the app builds these in `frontend/src/components/` with Tailwind and React 19.

## Button

The action control: one liquid Lens blue primary button per view, glass ghost buttons for everything else.

**Use primary** for the single next step the screen exists for: *Classify a tool*, *Add answers and run again*, *Draft documents*. A second primary on the same view means one of them is not the main step.

**Use ghost** for secondary actions beside it (*Edit description*, *Save draft*, *Download PDF*) and for small actions inside cards (*Change*).

Sizes: `md` (44 px) in the app, `lg` (52 px) on the landing page, `sm` (34 px) inside fact cards and rows.

The consumer provides the label, in sentence case, as a verb and its object. No arrows or chevrons in labels. Buttons never shrink in a row (`flex-shrink: 0`); when space runs out, the text beside them wraps.

### Motion

On hover the button lifts 1 px; the primary button also gets a liquid sheen that runs across it once. On press it settles back and scales to 98%. All of it uses `duration-press` and `ease-settle`, and turns off for reduced motion.

## SegmentedControl

A pill-shaped switch between two or three equal views of the same thing: the law version, the language, Summary or Reviewer.

Every app screen carries the law-version control top right (*As amended, 27 Jul 2026* / *Original, 2024*); the language control sits at the foot of the sidebar.

The consumer provides `label` (the group's accessible name) and the options. Keep option labels short; in German they grow by about 30%. Use it for views, not for answers to questions: those are a set of buttons with `aria-pressed` in a fact prompt.

### Motion

The selected option sits on a white glass pill that flows to the new choice: it first stretches to reach it (`liquid-stretch`, 160 ms), then draws its tail in under it (`liquid-settle`, 260 ms). Labels ease from slate to ink. Both labels share one weight so their widths never jump, and the pill is measured from the buttons, so any label fits. It re-measures once web fonts load, and moves instantly for reduced motion.

## GlassPanel

The surface everything sits on: frosted glass over the mist-and-mesh ground.

- `glass` for cards and panels: fill `glass-top` to `glass-bottom` at 150°, 1 px `glass-rim`, `blur-glass` with `saturate-glass`, `shadow-glass`.
- `thin` for chips, inner cards and tracks inside a glass panel.
- `dark` only for code examples and dark showcase tiles; text on it is `paper`.

Glass needs something to blur: put it on the mist ground with mesh lights (`mesh-blue`, `mesh-peach`, `mesh-teal`, `mesh-lilac`), never on a flat white page. Body text never sits on anything thinner than `thin`. Radius follows size: `card` (28 px) by default, `panel` (32 px) for the sidebar and the result card, `feature` (36 px) for landing panels.

### Motion

`glint` adds a soft light that follows the cursor across the glass (white at 20%, the `glint` token; 18% in the app). `lift` raises a card 3 px on hover with a deeper shadow, for cards that open something. Never use either on chat or long-reading panels: a conversation stays still under the cursor.

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

### Motion

The running step’s ring turns slowly; on load, steps resolve one after another in the Act’s order (170 ms apart). `paused` marks a step waiting for the user with a gentle Lens blue pulse; `error` marks a check that couldn’t finish, in plain red with its reason. Klar never shows a class after an error.

## ObligationItem

One duty on the to-do list: a checkbox, the duty in plain words, a link to its draft document if there is one, and the article.

Write the duty as an action the user takes (*Keep the logs it creates for at least six months*), not as the article's wording. The article sits right-aligned; its column is 86 px in English and at least 112 px in German (*Art. 26 Abs. 11*): pass `referenceWidth`. Wrap items in `<ul class="kl-obligations">`.

## FillMarker

A gap in a drafted document that only the user can fill: dashed Lens blue, never invented text.

Drafted documents contain only facts the user supplied or the classification established; everything else is a FillMarker that points to the guided interview (*To fill in. Answer in the interview on the right.*). Documents also carry the DRAFT StatusPill and the notice *Guidance, not legal advice.*

## ResultSummary

The top of every result: the class in Lexend, the wordmark's typeface, with its dot, the status, one sentence on role and basis, and the date duties apply from.

Order never changes: class first, then who you are and why (*You're the deployer. The tool is listed in Annex III, point 4(a): recruitment and selection of people.*), then the date. A High-risk result gets the warm glass tint and the orange dot glow; other classes stay plain glass. The legal-review line shows by default on High-risk, Prohibited and ambiguous results. The consumer provides every sentence and date; pass translated labels in German (*Hochrisiko*, *Ihre Pflichten gelten ab*).

## InventoryTable

Every AI tool the company uses in one glass table: tool and what it does, the company's role, the class, the basis, the date duties apply from, and the status.

Rows link to each tool's result. A decided row shows *Decided* as quiet text; open rows show their StatusPill so they stand out, and their class reads *High-risk, assumed* while a question or legal review is pending. Keep *what it does* to one line; it truncates rather than wraps. Put a company summary and a *needs you* list above it rather than extra columns.

The Class and Status columns are never narrower than their widest pill (*High-risk, assumed*, *Needs more information*, or longer in German), so a pill can't spill into the next column; the Tool column gives way instead, and its description truncates. Basis and Applies from give way too, breaking only between citations and words.

The Tool column keeps at least 160 px. To make room for it in German, two class pills wrap onto two lines inside the pill at 1280 px, and no others: *Außerhalb des Anwendungsbereichs* (261 px on one line) and *Hochrisiko, angenommen* (190 px). German class pills are capped at 160 px, the narrowest the out-of-scope pill gets on two lines (*Anwendungsbereichs* alone fills it); English ones at 200 px, which none reaches. The rule is a width cap, for German only and for assumed classes alike: any German class pill too wide to fit on one line in 160 px may wrap onto two lines inside its pill, whatever its text (*Verboten, angenommen*, 181 px, on an open prohibited result, is a third that would). Cells sit 12 px in from their neighbours rather than 16, without which the German table runs about 20 px past the panel's 958 (story P6, measured in `InventoryScreen.browser.test.tsx`). A tool without a result says why in quiet text, not a pill, and that text may wrap too.

## DescriptionField

Where a user describes a tool in their own words, with the four things worth mentioning and a reminder to leave out personal data.

It is the start of every classification, so keep it inviting: a few sentences are enough, and Klar asks for anything that decides the outcome. Detect the language from the text and say so near the actions (*Detected language: English*). The privacy line is required wherever people may type about applicants or staff; pass `privacyNote={null}` only where no personal data can appear.

## FactQuestion

A fact Klar had to assume, asked back in plain words with Yes, No and Not sure, and a line on why it matters.

Ask one fact per question, in the user's terms, not the Act's (*Did you put your own company name or brand on the tool?*, not *Is Art. 25(1)(a) engaged?*). The hint names the consequence and the provision (*If yes, you become the provider. Art. 25(1)(a)*). Preselect Klar's current assumption so the user sees what it believed. Stack several under a heading like *Please confirm 3 facts*; answering reruns the checks.

## ChatMessage

A question about a result and Klar's answer: the user's question in a Lens blue bubble on the right, Klar's answer in glass on the left with the provisions it rests on.

Klar's answers stay inside the AI Act and Commission guidance, lead with the direct answer (*Yes, and not only the rejected ones.*), and always carry at least one citation chip. They never say whether the company is compliant. Offer two or three follow-up questions as small glass buttons under the thread.

## VersionDiff

What changes between the original Act and the amended one for this result: a three-column comparison where only changed values are struck through and shown in Lens blue.

Show it in the reviewer view whenever the law version switch exists. List class, role and the date duties apply from; add a row only when it can differ. The note names the amending act and says plainly what did and didn't change (*The class didn't.*).

## InterviewPanel

The guided interview beside a draft document: progress, the questions already answered, the one being asked now, and what comes next.

Ask one question at a time and write the answer into the document exactly as given; say so under the field (*Written into the notice as you give it. Klar won't add anything you didn't say.*). *Skip for now* leaves a FillMarker in the document. Pair it with the automatic checks list (every required section present, no content the user didn't supply, facts match the classification).

## Timeline

Dates on a line, with a Today marker: filled dots for dates that have passed, rings for dates to come.

Use it for the AI Act's application dates on the landing page and anywhere a user needs to see what applies now and what later. Dates are exact (*2 Dec 2027*) and each carries one plain sentence on what applies. Keep it to four or five dates; more belongs in a table.

## Notice

The line every screen and every exported document carries: *Guidance, not legal advice. Klar is an AI system.*

Place it at the foot of the main column in `micro` type. Extend it where it helps (*Answers cite the consolidated AI Act (CELEX 02024R1689-20260727) …*), but never drop either half. In German: *Orientierungshilfe, keine Rechtsberatung. Klar ist ein KI-System.*

## Reveal

Content that arrives as it scrolls into view and leaves in reverse when you scroll back: the landing page's section rhythm.

- `variant="rise"` (default) fades in and rises 18 px over `duration-reveal`; `variant="focus"` also sharpens from a `focus-blur` blur, for section headings. *Klar* means clear, so headings come into focus.
- Stagger cards that have an order with `delay` in steps of the `stagger` token (110 ms): the four checks arrive 1, 2, 3, 4.
- Scrolling back up, a section leaves downward in `duration-exit` (500 ms), never staggered; one you scrolled past comes back from above.
- Content that is already on screen when the page loads stays put, so the static canvas, exports and screenshots always show the finished page. Reduced motion shows everything at once.

Use it for page sections, not for content inside the app's working screens: those settle in once on load instead (see the brand book's Motion section).

## Typewriter

A code example that types itself out like a streaming answer: the first line appears, then each line opens one character at a time with a Lens blue caret that blinks briefly at the end.

Use it once per page, for the agent or API example on `glass-dark`; it is a showcase, not a way to display text in the app. Timing comes from `type-char` (11 ms per character) with 70 ms between lines, so ten lines of JSON take about four seconds. The text must be monospaced: each line is revealed one character width at a time, never rewritten, so it can't shift the layout. It starts when it scrolls into view and, by default, types again each time it comes back. Reduced motion shows the finished text.

## MistGround

The page's backdrop: `mist` with the four mesh lights, plus two softer lights that drift at different speeds as the page scrolls and a Lens blue light that trails the cursor.

Everything sits behind the glass, so panels blur and refract the moving light: the page feels like light moving behind liquid glass, not like decoration. The cursor light follows with easing (9% of the distance per frame) and fades out when the pointer leaves. Use one per page, as the root of public pages. The app uses the static mist mesh without moving lights, so working screens stay calm. Turn parts off with `cursorLight={false}` or `drift={false}`; reduced motion turns both off.

## Composer

The question field: one white glass field with the send arrow tucked into its corner. It replaces a separate Ask button, so a reading screen stays quiet.

The arrow is slate on faint grey while the field is empty and turns into the Lens blue liquid button once there is a question; on hover the arrow lifts, and on send it flies up and back while the field clears. Enter asks, Shift+Enter adds a line; show that hint in `micro` text beside the law version note. The whole field gets a soft Lens blue focus ring. Pair it with `ChatMessage` threads and "Try asking" suggestions that fill the field.

## ChangeBanner

What a re-run changed, at the top of the result: the class before and after, one plain sentence on why, the run number and an undo.

Show it whenever an answer, a confirmed fact or an edited description changes the class. Lead with the cause in the user's words (*You said the shift planner uses only availability, contract hours and skills.*), then the consequence for the law (*That rules out Annex III point 4(b)*). Follow it with what changed in the inventory, obligations and "needs you" lists. The Lens blue edge marks it as Klar's update, not a warning.

## LawDate

A date the Digital Omnibus moved: shows the amended date by default and the original date when a `LawSwitch` above it picks *Original, 2024*.

Use it for every date that differs between the two texts, and only those: transparency (2 August 2026) and the prohibitions (2 February 2025) are the same in both, so write them as plain text.

## LawSwitch

The law version switch on every app screen: *As amended, 27 Jul 2026* or *Original, 2024*. Picking the original text swaps every date the Digital Omnibus moved and shows a `LawNotice`.

Wrap a screen in `.kl-law-scope` (or let it use the document) and write every moved date as a `LawDate`. The high-risk duties for Annex III apply from 2 December 2027 as amended, against 2 August 2026 in the original. The switch is a `SegmentedControl`, so its pill flows liquid-style between the two. Klar always classifies under the amended text by default; the original exists to explain the change, never as a way to plan.

## LawNotice

The line that appears under the top bar while the original 2024 text is selected: what you're viewing, what the Digital Omnibus moved, and that Klar uses the amended text by default.

It is hidden in the default view. Pass German text as children on German screens (*Sie sehen die ursprüngliche Fassung von 2024 …*).

## CheckCard

One of the Act's four checks, explained: its number in Lens blue, its name, the question it asks and the articles it rests on.

Always four, always in order (Scope, Prohibited practices, High-risk, Transparency), in a four-column grid with 20 px gaps. Write the question the check answers in plain words (*Does it match a banned use? If it does, the checks stop here.*). Numbers are allowed here because the order is the point.

## CheckCascade

The product in one picture: a description at the top, the Act's checks as staggered glass panes in their legal order, and the result they resolve into.

Use it as the hero's aside and anywhere Klar is explained at a glance. Show every check, in order, with its article. Only the check that decided the class opens (`outcome: 'hit'`): an orange ring, the quoted provision in Newsreader and the evidence tag for the fact it rests on. Use a real worked example, never lorem ipsum: the story must be legally right.

## CodePanel

A code or API example on dark glass: the one place `glass-dark` is used on a page.

Show real output of the MCP tools or API, trimmed to what the section is about, and pick out the value it's about with `highlight` (for a classification, the risk class). Every example keeps `law_version` and the notice field, because every result carries them. Comment lines (`//`) are for trimmed parts only.

## CtaBand

The landing page's closing invitation: one sentence that lowers the barrier, one line on the effort, one primary action.

It's the only glass panel with a cool blue tint. Keep the title specific and low-pressure (*Start with the tool you're least sure about.*) and the action identical to the nav's (*Classify a tool*).

## FeatureCard

A product feature: a small true-to-life preview on glass-thin, a title and one sentence on what it does for the user.

Previews are made of real components with real content (RiskPills in an inventory, ObligationItems with their articles, a DRAFT stamp on a document), never screenshots or illustrations. Three in a row: *AI inventory*, *Obligations checklist*, *Draft documents*.

## Hero

The landing page's opening: a dated badge, the question as the headline, one lead paragraph, two actions and a short note, with a CheckCascade beside it.

The headline asks the visitor's question (*Where does your AI tool stand under the AI Act?*); the lead says what Klar does in one breath. The badge dates the law version, so it must change when the law does. The note under the actions carries *Guidance, not legal advice.* One primary and one ghost button, never more.

## MetricTile

One published accuracy figure: the value, what it measures and on which cases.

**Never invent a figure.** Leave `value` out until the evaluation report has it: the tile then shows a Lens blue placeholder (`[—%]`) so an unmeasured number can't pass for a real one. Show the costliest error (*False low-risk rate*) next to the headline accuracy, and always say what the test set was. Use `.kl-ph` for any other placeholder in running text (*deleted after [RETENTION PERIOD]*).

## SectionHeader

A landing section's heading: a short, plain claim in `display-section` with a supporting lead beside it (or under it with `stacked`).

The title is a claim the section proves (*It checks in the Act's order, and shows its work.*), ending with a full stop. The lead explains how, in one or two sentences. Use `size="medium"` (44 px) inside feature panels such as the accuracy section. One SectionHeader per section, and no eyebrow labels above it.

## SiteFooter

The end of every public page: the guidance notice in bold, the statement that Klar is an AI system with how data is handled, and four plain links.

Name the providers and the retention period plainly; while the retention period is undecided, keep it as a `.kl-ph` placeholder rather than a guessed number. Links: *Method*, *Privacy*, *Source code*, and the showcase.

## SiteNav

The landing page's navigation: one floating glass pill with the logo, four section links, the language switch and the one primary action.

It floats 24 px below the top and 48 px in from the sides. Keep it to four links named for what a visitor wants to know (*How it works*, *Accuracy*, *For AI agents*, *Your data*) and one action (*Classify a tool*). The consumer provides the logo as an image from the Logos group.

## UncertaintyCard

One of the two honest outcomes when Klar isn't sure: the status, what it means, a small worked example and what happens next.

Show both side by side under *When it isn't sure, it says so.* *Needs more information* shows the question Klar asks with its answers; *Legally ambiguous* shows the two readings with their classes and says Klar works from the stricter one. Never replace these with a confidence score.

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
