import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import { playwright } from '@vitest/browser-playwright'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  // The router plugin must come before react(); it writes src/routeTree.gen.ts.
  // Tests sitting next to route files are not routes.
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
      routeFileIgnorePattern: '\\.test\\.tsx?$',
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  // The API's default CORS_ORIGINS (backend/aiact/settings.py) allow this origin; a busy port
  // fails instead of moving to one the API would refuse. Under Vitest (mode 'test') the browser
  // project's server inherits this setting, so there a busy port moves on instead: two worktrees
  // can run `pnpm test` at once (story F10).
  server: { port: 5173, strictPort: mode !== 'test' },
  build: {
    // No public source maps in production (frontend-security rule).
    sourcemap: false,
    // supabase-js, the heaviest library, gets its own chunk, downloaded beside the main one. Without
    // the group, once the result route shared TanStack Query with the app frame, the bundler merged
    // the user-data chunk (supabase-js with it) into the main bundle (about 600 kB).
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [{ name: 'supabase', test: /node_modules[\\/]@supabase[\\/]/ }],
        },
      },
    },
  },
  test: {
    // Tests run without Supabase, as in CI, whatever a developer's .env.local holds: tests that need
    // it stub it themselves, and "without Supabase" tests would otherwise see the local keys.
    env: { VITE_SUPABASE_URL: '', VITE_SUPABASE_ANON_KEY: '' },
    projects: [
      {
        // Component tests in jsdom: fast, no layout.
        extends: true,
        test: {
          name: 'unit',
          environment: 'jsdom',
          // Vitest's browser-mode default (the jsdom default is 5 s). A full run beside another
          // worktree's slows a test that loads a lazy route cold several-fold (F10).
          testTimeout: 15_000,
          include: ['src/**/*.test.{ts,tsx}'],
          exclude: ['src/**/*.browser.test.{ts,tsx}'],
          setupFiles: ['./src/test/setup.ts'],
        },
      },
      {
        // Layout tests that need a real engine (widths, sideways scrolling), in headless Chromium
        // with the real stylesheet: `*.browser.test.tsx`. Needs `pnpm exec playwright install chromium`.
        extends: true,
        test: {
          name: 'browser',
          include: ['src/**/*.browser.test.{ts,tsx}'],
          setupFiles: ['./src/test/browser-setup.ts'],
          browser: {
            enabled: true,
            headless: true,
            provider: playwright(),
            instances: [{ browser: 'chromium' }],
          },
        },
      },
    ],
  },
}))
