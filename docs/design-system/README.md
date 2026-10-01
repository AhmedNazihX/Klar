<!-- Copied from the Klar design system, https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4 (version 1790858064-dcaa, 2026-10-01). The artifact is the source: when it changes, re-copy this file. -->

# Klar

Klar classifies AI systems under the EU AI Act for small and medium companies. It runs the Act's checks in their legal order, cites the provision behind every step, and states how accurate it is. The design has one job: make an unclear legal case feel clear and checkable. Light passes through glass, the law is quoted in its own voice, and nothing is decided without showing why.

## Using this system

- Tokens are in `tokens.json`; the page compiles them to CSS custom properties with the same names (`--lens-blue`, `--radius-card`, `--shadow-glass`, `--font-sans`). Use the variables, never paste values.
- Fonts are hosted on Google Fonts: **Geist** 400/500/600/700, **Lexend** 500/600 and **Newsreader** (optical sizes 6–72, 400/500 and italic 400). `components/bundle.css` imports both.
- Components are React 18 components on `window.Klar` (`components/bundle.js`), styled by `components/bundle.css`. Props are documented in `components/index.d.ts`; each component's README says when to use it.
- Logos and icons are in the Logos and Icons asset groups. Copy them; never redraw the mark.
- Only a light theme is designed. There is no dark app theme yet; `glass-dark` is a surface for code and showcase tiles, not a theme.

## Voice and content

Klar talks to owners and managers of small companies, not lawyers. It is plain, exact and honest about what it doesn't know.

- **Say it plainly, then cite it.** Lead with the consequence in everyday words, then the provision: *You're the deployer. The tool is listed in Annex III, point 4(a): recruitment and selection of people.*
- **Duties are actions.** *Keep the logs it creates for at least six months*, not *Retention obligation under Article 26(6)*.
- **Show where facts came from.** Every deciding fact is *Stated*, *Inferred* or *Assumed*; assumed facts are always something the user can confirm or change.
- **Uncertainty is a status, not a percentage.** *Needs more information* names the missing fact and asks; *Legally ambiguous* shows both readings and works from the stricter one (*High-risk, assumed*). No confidence scores.
- **Never promise compliance.** Klar says what the Act requires; it never says a company *is compliant*. For High-risk and ambiguous results it recommends a legal review.
- **Two notices on every screen:** *Guidance, not legal advice.* and that Klar is an AI system.
- **Dates are exact and current:** *2 December 2027*, with the law version beside every result (*As amended, 27 Jul 2026*).
- **Buttons are verb and object, sentence case:** *Classify a tool*, *Add answers and run again*. No arrows in labels.

| Do | Don't |
|---|---|
| *Your duties apply from 2 December 2027.* | *Compliance deadline: Q4 2027!* |
| *This assessment is only as accurate as the description provided.* | *98% confident* |
| *Did you put your own company name or brand on the tool?* | *Confirm Art. 25(1)(a) applicability* |
| *When it isn't sure, it says so.* | *AI-powered certainty* |
| *Klar never guesses a class when a check fails, so there's no result yet.* | *Something went wrong. Showing best estimate.* |
| *"AI for HR" could be anything from a chatbot to a hiring tool. Add a sentence or two on each of these.* | *Invalid input* |
| *Your answer changed the result.* | *Classification updated successfully!* |
| *There's no route to comply: documentation or oversight can't make a prohibited practice allowed.* | *Mitigate this risk with our compliance toolkit* |

## Visual foundations

### Ground and glass

Every page sits on `mist` with up to four soft mesh lights (`mesh-blue` top left, `mesh-peach` top right, `mesh-teal` bottom, `mesh-lilac` a corner), each a large radial fading out at 62%. Content sits on liquid glass over that ground:

- **Glass** (cards, panels, the sidebar): fill from `glass-top` to `glass-bottom` at 150°, 1 px `glass-rim`, backdrop `blur-glass` with `saturate-glass`, and `shadow-glass` (a top highlight, a lower rim, an inner glow and a soft ink shadow).
- **Glass-thin** (chips, cards inside a panel, segmented tracks): `glass-thin`, `glass-thin-rim`, `blur-thin`, `shadow-glass-thin`.
- **Glass-dark** only for code and dark showcase tiles, with `paper` text.

Body text never sits on anything thinner than glass-thin. Glass needs the mesh behind it; on flat white it turns grey.

### Colour

- **Lens blue** (`lens-blue`) is the only brand colour: the primary button (a liquid gradient from `lens-blue-top` through `lens-blue` to `lens-blue-bottom`, with `shadow-button`), links, focus rings, selected states, and the last step of any sequence.
- **Ink** (`ink`, `ink-2`) for text; **slate** for muted text; **paper** on dark surfaces.
- **Risk colours** mean a risk class and nothing else. Each class has a text colour, a dot and a tint (`risk-high`, `risk-high-dot`, `risk-high-tint` …). They differ in lightness as well as hue, and they always come with their word. The brand never borrows them.

### Type: three voices

- **Geist is the product's voice**: every heading, label and sentence Klar writes. Headings are semibold with tight tracking (`heading-page` 40 px at −0.035em; `display-hero` 72 px at −0.045em on the landing page).
- **Newsreader is the Act's voice**: quoted provisions (`quote`) and drafted documents (`document-title`). If a line is the law's own wording, it is in the serif.
- **Lexend is Klar's verdict**: the risk class on a result (`verdict`, 64 px semibold; `verdict-small` on compact cards). It is the wordmark's typeface, rounded and made for reading, so the conclusion sounds like Klar: clear and calm, never a stamp.
- Text never goes below 12 px (`micro`, for the notice line).

### Shape and spacing

Rounded and soft, never sharp: pills (`radius-pill`) for every button, pill and control; `radius-card` (28 px) for cards, `radius-panel` (32 px) for the sidebar and the result card, `radius-feature` (36 px) for landing panels; `radius-tag` (7 px) only for evidence tags. The app sits 24 px (`space-6`) from the window edges: a 248 px glass sidebar, then the main column; cards are 20 px apart (`space-5`).

### Layout of a result

A result screen always follows the same order: the class and role first (the class in Lexend with its dot, role and Annex point in one sentence, the date duties apply from), then what to do, then the facts it rests on, then how Klar got there, then a question field. The legal-review line appears on every High-risk and ambiguous result.

## Building the screens

Every screen sits on the mist ground with a glass `SidebarNav` panel (248 px) and ends with a `Notice`.

- **Inventory**: a company summary in a `GlassPanel`, a *needs you* list, then `InventoryTable`.
- **Describe a tool**: `DescriptionField`, then `FactQuestion`s under *Please confirm N facts*; `CheckProgress` beside them while the checks run.
- **Result, summary**: `ResultSummary`, then *What you need to do* as `ObligationItem`s beside the `FactCard`s it rests on, then *How Klar got here* as `StepRow`s, then a question field.
- **Result, reviewer**: `StepCard`s with `Citation`s (the deciding one with `highlight`), beside `VersionDiff` and a `ChatMessage` thread.
- **Draft documents**: the document on white with a DRAFT `StatusPill` and `FillMarker`s, beside `InterviewPanel` and the automatic checks.
- **Landing page**: the hero with the step preview, `Timeline` for the dates, the four checks, the two uncertainty statuses, accuracy figures and the MCP example on `glass-dark`.
- **When the answer isn't straightforward**: *Not enough to start* replaces the fact questions with three prompts and waits; *Checks stopped* shows a `CheckProgress` step in `error` with Try again; *Needs more information* pauses at the deciding check (`paused`); after an answer, the re-run result opens with a `ChangeBanner`.
- **Provider path**: the result groups the provider duties as Build it right, Prove it and After launch (`ObligationItem`s), beside the SME simplified form and the internal-control route; the technical documentation is an Annex IV skeleton with drafted sections, `FillMarker` gaps and an `InterviewPanel`.
- **On a phone** (390 px): one column in the desktop's reading order, a compact `LawSwitch`, a `Composer`, and *Draft documents* full width at the end.
- **On paper**: the report for a lawyer is two A4 pages with the result, facts and sources, steps and provisions, duties, and a *For the reviewer* box with lines and a signature.
- **Site pages** (How it's measured, Privacy, Impressum, Contact) sit on a `MistGround` with the landing nav and footer; every unknown is a marked placeholder.
- **In German**: the landing page and the result follow the localisation section, quoting the official German text of the Act.

Every screen carries the law-version `SegmentedControl` top right, and a language `SegmentedControl` in the sidebar.

## Motion

Calm and exact. Things settle, nothing bounces, and anything with an order moves in the Act's order. Motion explains what is happening (a check resolving, a result coming into focus, a section arriving); it never decorates. Timing comes from the motion tokens: `ease-settle` for hover and exits, `ease-out` for entrances, `duration-hover` 350 ms, `duration-reveal` 900 ms, `duration-exit` 500 ms, `stagger` 110 ms.

Two rules hold everywhere. Nothing is hidden unless it starts off screen, so the static canvas, exports and screenshots always show the finished page. And `prefers-reduced-motion` turns all of it off: reveals show at once, switches move instantly, typed code appears complete.

### Public pages

- **On load, the hero resolves (2.6 s).** The headline comes into focus from a `focus-blur` blur (*klar* means clear). The four checks resolve in order, Scope, Prohibited, High-risk, Transparency, each tick landing in turn; the check that decided the class lights its orange ring; the result card settles and its verdict sharpens last.
- **On scroll, sections arrive** (`Reveal`). Headings come into focus; cards arrive in order, `stagger` apart; the timeline draws its Lens blue line to Today, placed at today's real date, and its dates appear one by one; the agent example types itself out (`Typewriter`).
- **Scrolling back up plays it in reverse.** A section leaving the bottom eases out downward in `duration-exit`, with no stagger; one you scrolled past comes back from above. Sections skipped in a jump still arrive from the side they are on.
- **The ground moves behind the glass** (`MistGround`). Two lights drift at different speeds as you scroll and a soft Lens blue light trails the cursor, so the glass visibly refracts. The nav stays on top and turns denser past the hero.
- **The language switch is liquid.** DE leads to the German page, where the pill flows from EN to DE on arrival.

### App screens

Working screens stay calm: they settle in once and then keep still.

- **On load**, panels settle in reading order 55 ms apart, the verdict comes into focus, check lists resolve 170 ms apart, chat messages arrive in turn and progress bars fill. The load motion clears after 3.5 s so it never fights hover.
- **While checks run**, the running step's ring turns slowly; a paused step (waiting for the user) pulses gently in Lens blue; a check that can't finish turns plain red with its reason.
- **The law version switch** flows like the language switch and swaps every date the Digital Omnibus moved (`LawDate`), with a `LawNotice` under the top bar.
- **The composer's arrow** is quiet until there is a question, lifts on hover and flies up on send.

### Hover

- **Glass catches the light**: a soft glint follows the cursor (`glint`, white at 20%; 18% in the app). Cards that open something lift 3 px on public pages and 2 px in the app.
- **The primary button** lifts 1 px and a liquid sheen runs across it once; pressed, it settles to 98%. Ghost buttons lift 1 px.
- **Nav links** draw a Lens blue underline from the left; rows, sidebar items and switches ease their colour and fill in 250 ms.
- **Not on conversations**: chat and long-reading panels get no glint, so a conversation stays still under the cursor.

## Iconography

A small line set on a 24 px grid: 1.8 px stroke (2.2–2.8 for small marks like check, plus and send), round caps and joins, no fills. In code use `Klar.Icon` (drawn in `currentColor`); the Icons asset group holds the same drawings as SVG files in `ink`. Icons label navigation and a few actions; they are never decoration and never replace a word.

## Logo

The logo is a speech bubble, because Klar answers questions, made of three layers of glass that run from dark `ink` through Lens blue to pale `logo-pale`: an unclear case, made clear. The wordmark *Klar* is Lexend SemiBold, outlined, with slightly softened corners; the l is trimmed to the K's height.

- Use the files in the Logos group; never rebuild the bubble or retype the wordmark.
- Clear space on every side: half the height of the capital K. Minimum size: 28 px tall for the lockup; below that use the app icon or favicon.
- On dark surfaces use *klar-lockup-on-dark*; for print, Word and PDF use *klar-lockup-flat* or *klar-lockup-mono*.
- Never recolour the layers with risk colours, never add effects, never put the logo on a busy photo without a glass panel behind it.

## Risk classes and statuses

| Label (EN) | Label (DE) | Tokens | Meaning |
|---|---|---|---|
| Prohibited | Verboten | `risk-prohibited` | Matches a practice banned by Art. 5 |
| High-risk | Hochrisiko | `risk-high` | Annex III or Annex I, and Art. 6(3) doesn't exempt it |
| Limited risk | Begrenztes Risiko | `risk-limited` | Transparency duties under Art. 50 |
| Minimal risk | Minimales Risiko | `risk-minimal` | No specific duties |
| Out of scope | Nicht erfasst | `risk-out` | Not an AI system, or the Act doesn't apply |
| Needs more information | Weitere Angaben nötig | dashed ink | A deciding fact is missing |
| Legally ambiguous | Rechtlich unklar | `status-ambiguous` | The law doesn't settle it; stricter reading applies |

## Accessibility

- Text meets 4.5:1 on its intended ground: every risk pill 6.2:1 or more on glass, `slate` 6.2:1 on mist, white on `lens-blue` 6.6:1, `paper` on glass-dark 11.7:1.
- Focus is a 2 px `lens-blue` outline with 2 px offset on every interactive element.
- Classes and statuses never rely on colour alone: word plus dot, or word plus a dashed outline.
- Segmented controls use `aria-pressed`; the live check list uses `aria-live="polite"`; decorative icons are `aria-hidden`.
- Motion is never the only signal: every state it shows is also in words. `prefers-reduced-motion` switches off every animation, transition, reveal and drifting light.
