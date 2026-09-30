<!-- Copied from the Klar design system, https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4 (version 1790766074-7ac5, 2026-09-30). The artifact is the source: when it changes, re-copy this file. -->

# Klar

Klar classifies AI systems under the EU AI Act for small and medium companies. It runs the Act's checks in their legal order, cites the provision behind every step, and states how accurate it is. The design has one job: make an unclear legal case feel clear and checkable. Light passes through glass, the law is quoted in its own voice, and nothing is decided without showing why.

## Using this system

- Tokens are in `tokens.json`; the page compiles them to CSS custom properties with the same names (`--lens-blue`, `--radius-card`, `--shadow-glass`, `--font-sans`). Use the variables, never paste values.
- Fonts are hosted on Google Fonts: **Geist** 400/500/600/700 and **Newsreader** (optical sizes 6–72, 400/500 and italic 400). `components/bundle.css` imports both.
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

### Type: two voices

- **Geist is the product's voice**: every heading, label and sentence Klar writes. Headings are semibold with tight tracking (`heading-page` 40 px at −0.035em; `display-hero` 72 px at −0.045em on the landing page).
- **Newsreader is the Act's voice**: quoted provisions (`quote`), the risk class on a result (`class-display`, 68 px) and drafted documents (`document-title`). If a line is the law's wording or the law's category, it is in the serif; otherwise it isn't.
- Text never goes below 12 px (`micro`, for the notice line).

### Shape and spacing

Rounded and soft, never sharp: pills (`radius-pill`) for every button, pill and control; `radius-card` (28 px) for cards, `radius-panel` (32 px) for the sidebar and the result card, `radius-feature` (36 px) for landing panels; `radius-tag` (7 px) only for evidence tags. The app sits 24 px (`space-6`) from the window edges: a 248 px glass sidebar, then the main column; cards are 20 px apart (`space-5`).

### Layout of a result

A result screen always follows the same order: the class and role first (class in Newsreader with its dot, role and Annex point in one sentence, the date duties apply from), then what to do, then the facts it rests on, then how Klar got there, then a question field. The legal-review line appears on every High-risk and ambiguous result.

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
