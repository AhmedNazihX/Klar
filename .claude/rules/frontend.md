---
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/**/*.css"
---

# Frontend rules (frontend/)

**Stack** (INIT › Tech stack): Vite, React and TypeScript, Tailwind CSS and shadcn/ui, TanStack Router and Query,
React Hook Form with Zod, and react-i18next.
- It's a **client-only single-page app**. There's no Next.js, no server components, no `"use client"`, and no server actions.
- Two data paths (INIT › Architecture: `UI → FastAPI` and `UI → DB`; user decision 2026-10-06):
  - Classification, Q&A, documents and anything that needs the engine go through the Python API (the generated client).
  - The user's own data (company profile, inventories, systems, import/export) goes straight to Supabase with
    `supabase-js`, under the anonymous session and row-level security. Don't wrap it in FastAPI endpoints.
  - The browser holds only the public anon key. Never a service-role key, and no access check that relies on the
    client: RLS policies and database constraints enforce ownership and validity.

**Files** (P4 sets these up and records them in `docs/LAYOUT.md`)
- shadcn primitives: `src/components/ui/<name>.tsx`, lower-case, added with the shadcn CLI. Change them sparingly.
- Feature components: `src/features/<feature>/<ComponentName>.tsx`, in PascalCase. Tests sit next to them: `<ComponentName>.test.tsx`.
- Hooks: `use-<name>.ts`, exporting `use<Name>`. Routes: `src/routes/` (TanStack Router, file-based).
- API client: `src/api/`. It's **generated** from `frontend/openapi.json`, so never edit it by hand. Regenerate it after the API changes.

**Data**
- Server data comes only through TanStack Query hooks that wrap the generated client or `supabase-js`. Never `fetch` inside `useEffect`,
  and never copy server data into client state.
- Shareable view state (filters, the selected system, the active tab, the law version) lives in the router's search params.
- Use the generated types for everything the API returns (`RiskClass`, `Status`, `ClassificationResult`). Never re-declare them.
- Forms use React Hook Form with a Zod schema.

**TypeScript:** explicit types on exported functions and props; `unknown` instead of `any`, then narrow; string literal
unions instead of `enum`. No `console.log` in committed code.

**React**
- Function components only. Follow the rules of hooks, and don't silence `exhaustive-deps`.
- `useEffect` is only for syncing with something outside React. Derive values during render.
- Memoise only for a memoised child, a hook dependency, or a measured cost. Keys must be stable IDs, never array indexes.
- Wrap every `Suspense` boundary in an error boundary (`react-error-boundary`).

**i18n:** every user-visible string goes through `t()`, with keys in both `en` and `de`. Don't build sentences by
joining strings. Format dates and numbers with `Intl`, using the active locale.

**Result views** (the product's point, INIT › Users and positioning)
- The "guidance, not legal advice" notice and the AI disclosure (Art. 50(1)) are always visible on results and documents.
- Show the law version and the as-of date.
- `needs_more_information` and `legally_ambiguous` are shown as their own states, never styled like a decided class.
  The working assumption is labelled as one.
- A citation shows its provision ID and the quoted text. Guidance that exists only in English is labelled as such.
- The reviewer view shows each step's fact and evidence tag (stated, inferred or assumed).

**Look and feel:** the goal is trust through clarity, for non-experts reading legal results.
- Plain hierarchy, readable type and generous line length. Use colour for meaning, such as risk class and status, and always with text too, never colour alone.
- WCAG 2.2 AA, full keyboard use, visible focus, and respect for `prefers-reduced-motion`.
- Style with Tailwind and the shadcn CSS variables. Don't hard-code colours.
- The visual direction is the user's Design canvas (`docs/BACKLOG.md` › Phase 5 › Design reference). Use the `frontend-design` skill only for gaps, not here.
