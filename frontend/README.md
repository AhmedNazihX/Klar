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

## Commands

- `corepack pnpm dev`: the app on the Vite dev server
- `corepack pnpm lint`: ESLint
- `corepack pnpm build`: type check and production build
- `corepack pnpm test`: all tests, jsdom (`unit`) and Chromium (`browser`)
- `corepack pnpm exec vitest run --project unit`: only the jsdom tests, no browser needed
- `corepack pnpm format`: Prettier
- `corepack pnpm gen:api`: regenerate `src/api/` from `openapi.json`
