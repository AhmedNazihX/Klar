// The Ask page's layout in a real browser: with an answer citing long guideline names on screen,
// nothing scrolls sideways on a 390 px phone, in German too (the longest names), and each chip
// keeps its whole name.
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import type { Citation } from '@/api'
import { answered } from '@/test/qa-fixtures'
import { renderRoute } from '@/test/test-utils'

import { ASK_THREAD, writeThread } from './qa-history'

const PHONE = { width: 390, height: 844 } as const

function guidance(provisionId: string, documentId: string): Citation {
  return {
    provision_id: provisionId,
    document_id: documentId,
    law_version: null,
    document_status: 'final',
    language: 'en',
    quote: 'The guidelines explain the duty.',
    english_only: true,
    changed_by_omnibus: false,
  }
}

/** An answered question citing the guidance with the longest names, kept for the session. */
function seedThread(): void {
  const answer = answered({
    citations: [
      guidance('guide:guide-art50:para:12', 'guide-art50'),
      guidance('guide:guide-high-risk-annex-iii:para:123', 'guide-high-risk-annex-iii'),
      guidance('guide:guide-prohibited:para:245', 'guide-prohibited'),
    ],
  })
  writeThread(ASK_THREAD, [
    { id: 'q1', question: 'Do the Article 50 duties apply?', state: 'answered', answer },
  ])
}

/** How far the page reaches past the window's right edge, in px (0 when nothing sticks out). */
function sidewaysOverflow(): number {
  const root = document.documentElement
  return root.scrollWidth - root.clientWidth
}

afterEach(() => {
  window.sessionStorage.clear()
})

describe('the Ask page at 390 px', () => {
  it.each(['en', 'de'] as const)(
    'with an answer citing long guideline names does not scroll sideways (%s)',
    async (language) => {
      await page.viewport(PHONE.width, PHONE.height)
      seedThread()
      await i18n.changeLanguage(language)
      renderRoute('/app/ask')
      await screen.findByRole('heading', { level: 1 })
      await document.fonts.ready

      const chips = screen.getByRole('list', {
        name: language === 'de' ? 'Zitierte Vorschriften' : 'Provisions cited',
      })
      const buttons = within(chips).getAllByRole('button')
      expect(buttons).toHaveLength(3)
      for (const chip of buttons) {
        // The whole name is shown: the chip wraps it instead of cutting or overflowing it.
        expect(chip.scrollWidth, chip.textContent).toBeLessThanOrEqual(chip.clientWidth)
      }
      expect(sidewaysOverflow()).toBe(0)
    },
  )
})
