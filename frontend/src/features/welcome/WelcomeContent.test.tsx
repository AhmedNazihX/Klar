import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS, userDataHandlers } from '@/test/user-data-handlers'

import type { QuotedProvision } from './LawQuote'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

beforeEach(() => {
  server.use(
    ...userDataHandlers(
      () => [],
      () => 0,
    ),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

async function openWelcome(path = '/app/welcome') {
  const user = userEvent.setup()
  renderRoute(path)
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  return user
}

// A quote is found by its source line (the locale's), then checked for a few of its words.
function citationBySource(provision: QuotedProvision): HTMLElement {
  const caption = screen.getByText(i18n.t(`welcome.law.${provision}.source`))
  const figure = caption.closest('figure')
  if (!figure) throw new Error('the source line is not in a Citation')
  return figure
}

describe('Welcome, the derived size line', () => {
  it('shows nothing until both bands are chosen', async () => {
    const user = await openWelcome()
    await user.click(screen.getByRole('button', { name: '10–49' }))
    expect(screen.queryByText('Counts as an SME')).not.toBeInTheDocument()
  })

  it('names an SME and quotes Art. 99(3) and Art. 99(6) with their sources', async () => {
    const user = await openWelcome()
    await user.click(screen.getByRole('button', { name: '10–49' }))
    await user.click(screen.getByRole('button', { name: 'Up to €50 m' }))
    expect(screen.getByText('Counts as an SME')).toBeInTheDocument()
    expect(citationBySource('art99_6')).toHaveTextContent('In the case of SMEs')
    expect(citationBySource('art99_3')).toHaveTextContent('whichever is higher')
  })

  it('names a small mid-cap, and says it may still be an SME by balance sheet', async () => {
    const user = await openWelcome()
    await user.click(screen.getByRole('button', { name: '50–249' }))
    await user.click(screen.getByRole('button', { name: 'Up to €150 m' }))
    expect(screen.getByText('Counts as a small mid-cap')).toBeInTheDocument()
    expect(screen.getByText(/may still count as an SME/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '250–749' }))
    expect(screen.queryByText(/may still count as an SME/)).not.toBeInTheDocument()
  })

  it.each(['en', 'de'] as const)(
    'cites Art. 99(6a), not Art. 99(6), for a small mid-cap (%s)',
    async (language) => {
      const user = await openWelcome()
      await act(() => i18n.changeLanguage(language))
      await user.click(screen.getByRole('button', { name: '250–749' }))
      await user.click(
        screen.getByRole('button', { name: i18n.t('welcome.turnoverBand.up_to_50m') }),
      )
      expect(screen.getByText(i18n.t('welcome.size.label.smc'))).toBeInTheDocument()
      expect(screen.getByText(i18n.t('welcome.size.body.smc'))).toHaveTextContent(/99.*6a/)
      expect(citationBySource('art99_6a')).toHaveTextContent(i18n.t('welcome.law.art99_6a.quote'))
      expect(screen.queryByText(i18n.t('welcome.law.art99_6.source'))).not.toBeInTheDocument()
    },
  )

  it('names neither above the small mid-cap bands, with the balance-sheet caveats', async () => {
    const user = await openWelcome()
    await user.click(screen.getByRole('button', { name: '1–9' }))
    await user.click(screen.getByRole('button', { name: 'More' }))
    expect(screen.getByText('Neither an SME nor a small mid-cap')).toBeInTheDocument()
    expect(screen.getByText(/Art\. 99\(3\) to \(5\)/)).toBeInTheDocument()
    expect(screen.getByText(/may still count as an SME/)).toBeInTheDocument()
    expect(screen.getByText(/may still count as a small mid-cap/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '250–749' }))
    expect(screen.queryByText(/may still count as an SME/)).not.toBeInTheDocument()
    expect(screen.getByText(/may still count as a small mid-cap/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '750+' }))
    expect(screen.queryByText(/may still count/)).not.toBeInTheDocument()
  })
})

describe('Welcome, the size line under the original 2024 text', () => {
  it('shows no small mid-cap and no Art. 99(6a)', async () => {
    const user = await openWelcome('/app/welcome?law=original')
    await user.click(screen.getByRole('button', { name: '250–749' }))
    await user.click(screen.getByRole('button', { name: 'Up to €50 m' }))
    expect(screen.getByText('Not an SME')).toBeInTheDocument()
    expect(screen.queryByText('Counts as a small mid-cap')).not.toBeInTheDocument()
    expect(screen.getByText(/no small mid-cap rules/)).toBeInTheDocument()
    expect(screen.queryByText(/simplified documentation/)).not.toBeInTheDocument()
    expect(screen.queryByText(i18n.t('welcome.law.art99_6a.source'))).not.toBeInTheDocument()
    expect(citationBySource('art99_6')).toHaveTextContent('In the case of SMEs')
  })

  it('keeps the SME line, which reads the same in both texts', async () => {
    const user = await openWelcome('/app/welcome?law=original')
    await user.click(screen.getByRole('button', { name: '10–49' }))
    await user.click(screen.getByRole('button', { name: 'Up to €10 m' }))
    expect(screen.getByText('Counts as an SME')).toBeInTheDocument()
    expect(citationBySource('art99_6')).toBeInTheDocument()
  })
})

describe('Welcome, where you are established', () => {
  it('cites Art. 2(1)(c) and Art. 22 in the hint, and quotes both outside the EU', async () => {
    const user = await openWelcome()
    const field = screen.getByLabelText('Where you are established')
    expect(field).toHaveAccessibleDescription(/Art\. 2\(1\)\(c\).*Art\. 22/)
    expect(screen.queryByText(i18n.t('welcome.law.art2_1_c.source'))).not.toBeInTheDocument()

    await user.selectOptions(field, 'CH')
    expect(citationBySource('art2_1_c')).toHaveTextContent('third country')
    expect(citationBySource('art22_1')).toHaveTextContent('authorised representative')

    await user.selectOptions(field, 'FR')
    expect(screen.queryByText(i18n.t('welcome.law.art2_1_c.source'))).not.toBeInTheDocument()
  })

  it('gives the hint and both quotes in German', async () => {
    const user = await openWelcome()
    await act(() => i18n.changeLanguage('de'))
    const field = screen.getByLabelText('Wo Sie niedergelassen sind')
    expect(field).toHaveAccessibleDescription(/Art\. 2 Abs\. 1 Buchst\. c.*Art\. 22/)

    await user.selectOptions(field, 'CH')
    expect(
      screen.getByText('Art. 2 Abs. 1 Buchst. c, Verordnung (EU) 2024/1689, Deutsch'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Art. 22 Abs. 1, Verordnung (EU) 2024/1689, Deutsch'),
    ).toBeInTheDocument()
    expect(citationBySource('art2_1_c')).toHaveTextContent('Drittland')
    expect(citationBySource('art22_1')).toHaveTextContent('Bevollmächtigten')
  })

  it('no longer says the field decides the supervising authority', async () => {
    await openWelcome()
    expect(screen.queryByText(/national authority/)).not.toBeInTheDocument()
  })
})

describe('Welcome, the rest of the screen', () => {
  it('shows the empty tools state, how it works and the 30 days', async () => {
    await openWelcome()
    const tools = screen.getByRole('region', { name: 'Your AI tools' })
    expect(within(tools).getByText('No tools yet')).toBeInTheDocument()
    expect(within(tools).getByRole('link', { name: 'Classify your first tool' })).toHaveAttribute(
      'href',
      '/app/classify',
    )
    expect(within(tools).getByLabelText('Import your data')).toBeInTheDocument()
    const how = screen.getByRole('region', { name: 'How it works' })
    expect(within(how).getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText(/deleted after 30 days without activity/)).toBeInTheDocument()
  })

  it('is in German, quotes included', async () => {
    const user = await openWelcome()
    await act(() => i18n.changeLanguage('de'))
    expect(screen.getByRole('heading', { name: 'Über Ihr Unternehmen', level: 2 })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Vorerst überspringen' })).toBeInTheDocument()
    expect(screen.getByText('Noch keine Tools')).toBeInTheDocument()
    expect(screen.getByText(/nach 30 Tagen ohne Aktivität gelöscht/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '1–9' }))
    await user.click(screen.getByRole('button', { name: 'Bis 10 Mio. €' }))
    expect(screen.getByText('Gilt als KMU')).toBeInTheDocument()
    expect(citationBySource('art99_6')).toHaveTextContent('Im Falle von KMU')
  })
})
