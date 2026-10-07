import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import { playwright } from '@vitest/browser-playwright'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
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
  // fails instead of moving to one the API would refuse.
  server: { port: 5173, strictPort: true },
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
    projects: [
      {
        // Component tests in jsdom: fast, no layout.
        extends: true,
        test: {
          name: 'unit',
          environment: 'jsdom',
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
})
