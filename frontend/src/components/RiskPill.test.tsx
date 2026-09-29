import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { PILL_KINDS } from './pill-kinds'
import { RiskPill } from './RiskPill'

const ENGLISH = {
  prohibited: 'Prohibited',
  high_risk: 'High-risk',
  limited_risk: 'Limited risk',
  minimal_risk: 'Minimal risk',
  out_of_scope: 'Out of scope',
  legally_ambiguous: 'Legally ambiguous',
  needs_more_information: 'Needs more information',
} as const

function renderAllPills(): void {
  renderWithProviders(
    <ul>
      {PILL_KINDS.map((kind) => (
        <li key={kind}>
          <RiskPill kind={kind} />
        </li>
      ))}
    </ul>,
  )
}

describe('RiskPill', () => {
  it.each(PILL_KINDS)('shows the word for %s, not just a colour', async (kind) => {
    renderWithProviders(<RiskPill kind={kind} />)
    expect(await screen.findByText(ENGLISH[kind])).toBeInTheDocument()
  })

  it('shows every class and status in German', async () => {
    await i18n.changeLanguage('de')
    renderAllPills()
    for (const label of [
      'Verboten',
      'Hochrisiko',
      'Begrenztes Risiko',
      'Minimales Risiko',
      'Außerhalb des Anwendungsbereichs',
      'Rechtlich unklar',
      'Weitere Angaben nötig',
    ]) {
      expect(await screen.findByText(label)).toBeInTheDocument()
    }
  })

  it('gives the uncertain statuses a look of their own, without the class dot', async () => {
    renderAllPills()
    const decided = await screen.findByText('High-risk')
    const ambiguous = screen.getByText('Legally ambiguous')
    const moreInfo = screen.getByText('Needs more information')

    expect(decided.querySelector('[aria-hidden="true"]')).not.toBeNull()
    expect(ambiguous.querySelector('[aria-hidden="true"]')).toBeNull()
    expect(moreInfo.querySelector('[aria-hidden="true"]')).toBeNull()
    expect(moreInfo).toHaveClass('border-dashed')
    expect(decided).toHaveClass('text-risk-high', 'text-[13px]')
  })
})
