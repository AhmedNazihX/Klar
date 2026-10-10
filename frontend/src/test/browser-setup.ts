// Set-up for the browser project (`*.browser.test.tsx`, real Chromium): the app's real
// stylesheet and fonts, i18n, and the jest-dom matchers. No MSW: these tests make no requests.
import '@testing-library/jest-dom/vitest'
import '@/index.css'
import '@/i18n'

import { cleanup, configure } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, beforeEach } from 'vitest'

import { FIRST_RENDER_MS } from './timeouts'

// A screen's first render loads its lazy route chunks cold; findBy* and waitFor wait this long.
configure({ asyncUtilTimeout: FIRST_RENDER_MS })

beforeEach(async () => {
  window.localStorage.clear()
  await i18n.changeLanguage('en')
})
afterEach(() => {
  cleanup()
})
