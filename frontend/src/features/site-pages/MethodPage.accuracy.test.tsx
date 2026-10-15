import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { MethodPage } from './MethodPage'

// The page's default figures are the committed accuracy.json, not a prop the route must pass:
// with measured values in that file, <MethodPage /> on its own shows them. In a file of its own,
// as the mock replaces accuracy.json for every test in the file.
vi.mock('@/content/accuracy.json', () => ({
  default: {
    risk_class_accuracy: { value: 0.875, run_id: 'run-a' },
    false_low_risk_rate: { value: 0.04, run_id: 'run-a' },
    citations_exist: { value: 1, run_id: 'run-a' },
    head_to_head: {
      klar: { value: 0.8, run_id: 'run-b' },
      checker: { value: 0.55, run_id: 'run-b' },
      checker_name: 'the Commission checker',
      cases: 24,
    },
    scored_cases: { count: 140, run_id: 'run-a' },
    own_cases: { count: 60, run_id: 'run-c' },
    run_date: '2026-11-02',
    report: 'eval/reports/final.md',
    run_ids: ['run-a', 'run-b'],
    note: 'A made-up run.',
  },
}))

describe('the method figures by default', () => {
  it('show what accuracy.json measured', async () => {
    await i18n.changeLanguage('en')
    renderWithProviders(<MethodPage />)
    const counted = await screen.findByRole('region', { name: 'What we count' })
    expect(
      within(counted)
        .getAllByRole('listitem')
        .map((tile) => tile.firstElementChild?.textContent),
    ).toEqual(['87.5%', '4%', '100%', '80%vs55%'])
  })
})
