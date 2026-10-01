import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState, type JSX } from 'react'
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
  vi.restoreAllMocks()
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

  it('re-measures the pill when the labels change width while the choice stays', async () => {
    // jsdom has no layout or ResizeObserver: a button is 10 px per character, and the observer
    // reports every observed button when `resize` is called.
    vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockImplementation(function (
      this: HTMLElement,
    ) {
      return this.textContent.length * 10
    })
    const observers: { callback: ResizeObserverCallback; targets: Element[] }[] = []
    vi.stubGlobal(
      'ResizeObserver',
      class {
        private readonly entry: { callback: ResizeObserverCallback; targets: Element[] }
        constructor(callback: ResizeObserverCallback) {
          this.entry = { callback, targets: [] }
          observers.push(this.entry)
        }
        observe(target: Element): void {
          this.entry.targets.push(target)
        }
        unobserve(): void {}
        disconnect(): void {
          this.entry.targets = []
        }
      },
    )
    function resize(): void {
      for (const { callback, targets } of observers) {
        if (targets.length > 0) callback([], {} as ResizeObserver)
      }
    }
    function Labels(): JSX.Element {
      const [isLong, setIsLong] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setIsLong(true)}>
            Longer labels
          </button>
          <SegmentedControl
            label="View"
            options={[
              { value: 'summary', label: isLong ? 'Zusammenfassung' : 'Summary' },
              { value: 'reviewer', label: 'Reviewer' },
            ]}
          />
        </>
      )
    }
    const user = userEvent.setup()
    renderWithProviders(<Labels />)
    await screen.findByRole('button', { name: 'Summary' })
    expect(thumb().style.width).toBe('70px')

    await user.click(screen.getByRole('button', { name: 'Longer labels' }))
    expect(screen.getByRole('button', { name: 'Zusammenfassung' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    resize()

    expect(thumb().style.width).toBe('150px')
    expect(thumb().style.transition).toBe('none')
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
