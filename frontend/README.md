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
- `corepack pnpm e2e`: the end-to-end tests (below)
- `corepack pnpm format`: Prettier
- `corepack pnpm gen:api`: regenerate `src/api/` from `openapi.json`

## End-to-end tests

Playwright drives the built app in Chromium through the main flows (`e2e/*.spec.ts`, story P13):
the first visit, the worked example's result and its follow-up questions, the inventory, a duty
ticked on Obligations, the PDF and Word downloads, delete-my-data, a 390 px phone, German, colour
contrast and reduced motion. Nothing is live and nothing is paid for:

- **The API runs in replay mode** (`backend/tests/e2e/replay_server.py`): the real app, with each
  classification replayed from recorded model replies (INIT's worked example, and the runs in
  `e2e/runs.json` once recorded). A request without a recording ends in the app's "stopped"
  state; nothing reaches the network.
- **Supabase is a stack of its own** (`e2e/supabase/config.toml`: Postgres, Auth and the REST
  API on 54331-54332), beside the backend's test database and never the hosted project: the
  build takes its URL and key from `supabase status`, whatever `.env.local` says.

Run, from the repo root:

```sh
make e2e-db   # once: starts the e2e stack and loads the corpus into it
make e2e      # builds the app, starts the replay API (8766) and `vite preview` (4174), runs the flows
```

The servers start and stop with the run, on their own ports, so `make dev` (8000, 5173) can keep
running. The e2e stack applies the migrations and the obligations seed only when it is created:
after a new migration or a seed change, recreate it with
`supabase stop --workdir frontend/e2e --no-backup`, then `make e2e-db`.

A flow on a run that isn't recorded yet (`e2e/runs.json`) runs until the app shows the run
stopped for want of its recording, then ends there as an expected failure (`test.fail`) that
names the command that records it: `cd backend && uv run pytest tests/e2e/test_e2e_runs.py
--record-mode=once` (live, paid model calls). Any other failure, before that point or a run that
doesn't stop, fails the flow. A flow also checks that the app's request still matches the
recorded one. The downloaded PDF and Word files are read back with the backend's own test reader
(`backend/tests/export/reading.py`), so the run needs the backend's environment (`uv sync`).
