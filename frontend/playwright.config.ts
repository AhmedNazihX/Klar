// End-to-end tests (story P13): the built app in Chromium, against the API in replay mode and the
// e2e Supabase stack. `corepack pnpm e2e`; set-up in README.md › End-to-end tests.
import { defineConfig, devices } from '@playwright/test'

import { API_PORT, API_URL, WEB_PORT, WEB_URL, supabaseStack } from './e2e/stack.ts'

const isCI = Boolean(process.env.CI)
const supabase = supabaseStack()
const BUILD_DIR = 'dist-e2e'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: isCI,
  // A flaky flow is fixed, not retried.
  retries: 0,
  // A few at once: worktrees run their checks side by side (F10), and the API renders files in
  // eight workers (backend/tests/e2e/replay_server.py, PARALLEL_SLOTS).
  workers: isCI ? 2 : 4,
  reporter: isCI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  // A classification replays in about a second; the first page load builds nothing (preview).
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: WEB_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Never a server that is already running: the ports are the run's own, and a stale server
  // would test old code.
  webServer: [
    {
      name: 'api',
      command: `uv run --directory ../backend python -m tests.e2e.replay_server --port ${API_PORT} --origin ${WEB_URL}`,
      url: `${API_URL}/openapi.json`,
      reuseExistingServer: false,
      timeout: 120_000,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
    {
      name: 'web',
      command:
        `corepack pnpm exec vite build --outDir ${BUILD_DIR} --emptyOutDir && ` +
        `corepack pnpm exec vite preview --outDir ${BUILD_DIR} --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 180_000,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
      // The process environment beats .env.local, so the build never sees the hosted project.
      env: {
        VITE_API_URL: API_URL,
        VITE_SUPABASE_URL: supabase.url,
        VITE_SUPABASE_ANON_KEY: supabase.anonKey,
      },
    },
  ],
})
