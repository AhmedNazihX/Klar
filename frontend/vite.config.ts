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
  build: {
    // No public source maps in production (frontend-security rule).
    sourcemap: false,
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
