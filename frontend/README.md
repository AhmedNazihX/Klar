# Klar frontend

Vite, React and TypeScript. Run everything from `frontend/`.

## Set-up (once per clone)

```sh
corepack pnpm install --frozen-lockfile
corepack pnpm exec playwright install chromium
```

The second line downloads the headless Chromium that `pnpm test` needs: layout tests
(`*.browser.test.tsx`, Vitest's `browser` project) run in a real browser. On a fresh CI runner use
`corepack pnpm exec playwright install --with-deps chromium`.

Copy `.env.example` to `.env.local` and fill in the hosted Supabase project's URL and publishable
key (decision 034): the app runs against the hosted project. The tests don't read them; their
Supabase calls go to fixtures.

## Commands

- `corepack pnpm dev`: the app on the Vite dev server
- `corepack pnpm lint`: ESLint
- `corepack pnpm build`: type check and production build
- `corepack pnpm test`: all tests, jsdom (`unit`) and Chromium (`browser`). Several worktrees can
  run it at once: the browser project's server starts at port 63315 and moves to the next free
  port when that one is taken (only `pnpm dev` keeps a fixed port, 5173)
- `corepack pnpm exec vitest run --project unit`: only the jsdom tests, no browser needed
- `corepack pnpm format`: Prettier
- `corepack pnpm gen:api`: regenerate `src/api/` from `openapi.json`
