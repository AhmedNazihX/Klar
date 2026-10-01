import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { STATUSES } from './pill-kinds'
import { StatusPill } from './StatusPill'

const ENGLISH = {
  decided: 'Decided',
  ambiguous: 'Legally ambiguous',
  'needs-info': 'Needs more information',
  draft: 'DRAFT',
} as const

describe('StatusPill', () => {
  it.each(STATUSES)('shows the word for %s', async (status) => {
    renderWithProviders(<StatusPill status={status} />)
    expect(await screen.findByText(ENGLISH[status])).toHaveAttribute('data-status', status)
  })

  it('gives each status its own look: dashed needs-info, purple ambiguous, the DRAFT stamp', async () => {
    renderWithProviders(
      <>
        {STATUSES.map((status) => (
          <StatusPill key={status} status={status} />
        ))}
      </>,
    )
    expect(await screen.findByText('Needs more information')).toHaveClass('border-dashed')
    expect(screen.getByText('Legally ambiguous')).toHaveClass('text-status-ambiguous')
    expect(screen.getByText('DRAFT')).toHaveClass('text-risk-high', 'tracking-[0.08em]')
    expect(screen.getByText('Decided')).toHaveClass('text-ink-2')
  })

  it('speaks German and takes a label override', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(
      <>
        <StatusPill status="needs-info" />
        <StatusPill status="decided" size="sm">
          Lauf 2
        </StatusPill>
      </>,
    )
    expect(await screen.findByText('Weitere Angaben nötig')).toBeInTheDocument()
    expect(screen.getByText('Lauf 2')).toHaveClass('text-xs')
  })
})
