import '@testing-library/jest-dom/vitest'
import '@/i18n'

import { cleanup, configure } from '@testing-library/react'
import i18n from 'i18next'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import { server } from './msw-server'
import { FIRST_RENDER_MS } from './timeouts'

// A screen's first render loads its lazy route chunks cold; findBy* and waitFor wait this long.
configure({ asyncUtilTimeout: FIRST_RENDER_MS })

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
  // jsdom has no scrolling; the router's scroll restoration calls this.
  window.scrollTo = () => undefined
})
beforeEach(async () => {
  window.localStorage.clear()
  await i18n.changeLanguage('en')
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
