import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubReducedMotion } from '@/test/reduced-motion'
import { renderWithProviders } from '@/test/test-utils'

import { SegmentedControl } from './SegmentedControl'

const OPTIONS = [
  { value: 'summary', label: 'Summary' },
  { value: 'reviewer', label: 'Reviewer' },
] as const

function thumb(): HTMLElement {
  const group = screen.getByRole('group', { name: 'View' })
  const pill = group.querySelector<HTMLElement>('[aria-hidden="true"]')
  if (!pill) throw new Error('the segmented control has no pill')
  return pill
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SegmentedControl', () => {
  it('marks the chosen option with aria-pressed and reports a change', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(<SegmentedControl label="View" options={OPTIONS} onChange={onChange} />)

    const summary = await screen.findByRole('button', { name: 'Summary' })
    const reviewer = screen.getByRole('button', { name: 'Reviewer' })
    expect(summary).toHaveAttribute('aria-pressed', 'true')
    expect(reviewer).toHaveAttribute('aria-pressed', 'false')

    await user.click(reviewer)

    expect(onChange).toHaveBeenCalledExactlyOnceWith('reviewer')
    expect(reviewer).toHaveAttribute('aria-pressed', 'true')
    expect(summary).toHaveAttribute('aria-pressed', 'false')
  })

  it('follows a controlled value and ignores a click on the chosen option', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(
      <SegmentedControl label="View" options={OPTIONS} value="reviewer" onChange={onChange} />,
    )
    const reviewer = await screen.findByRole('button', { name: 'Reviewer' })
    await user.click(reviewer)
    expect(onChange).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Summary' }))
    expect(onChange).toHaveBeenCalledExactlyOnceWith('summary')
    // Controlled: the parent did not change the value, so the choice stays.
    expect(reviewer).toHaveAttribute('aria-pressed', 'true')
  })

  it('flows the pill: stretches over liquid-stretch, then settles over liquid-settle', async () => {
    stubReducedMotion(false)
    const user = userEvent.setup()
    renderWithProviders(<SegmentedControl label="View" options={OPTIONS} />)
    await screen.findByRole('button', { name: 'Summary' })
    expect(thumb().style.transition).toBe('none')

    await user.click(screen.getByRole('button', { name: 'Reviewer' }))

    expect(thumb().style.transition).toContain('var(--liquid-stretch) var(--ease-settle)')
    await waitFor(() => {
      expect(thumb().style.transition).toContain('var(--liquid-settle) var(--ease-out)')
    })
  })

  it('moves the pill instantly for reduced motion', async () => {
    stubReducedMotion(true)
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })
    renderWithProviders(<SegmentedControl label="View" options={OPTIONS} />)

    await user.click(await screen.findByRole('button', { name: 'Reviewer' }))
    // No settle step is scheduled either.
    vi.runAllTimers()
    vi.useRealTimers()

    expect(thumb().style.transition).toBe('none')
    expect(screen.getByRole('button', { name: 'Reviewer' })).toHaveAttribute('aria-pressed', 'true')
  })
})
