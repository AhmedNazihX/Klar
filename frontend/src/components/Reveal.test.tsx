import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { stubIntersectionObserver } from '@/test/intersection-observer'
import { stubReducedMotion } from '@/test/reduced-motion'

import { Reveal } from './Reveal'

const WINDOW_HEIGHT = 800

/** Puts `element` at `top` px from the top of the window, 200 px tall. */
function placeAt(element: Element, top: number): void {
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(
    DOMRect.fromRect({ x: 0, y: top, width: 400, height: 200 }),
  )
}

function renderReveal(variant: 'rise' | 'focus' = 'rise', delay = 0): HTMLElement {
  render(
    <Reveal variant={variant} delay={delay}>
      <p>Section</p>
    </Reveal>,
  )
  const element = screen.getByText('Section').parentElement
  if (!element) throw new Error('no Reveal wrapper')
  return element
}

describe('Reveal', () => {
  let observer: ReturnType<typeof stubIntersectionObserver>

  beforeEach(() => {
    stubReducedMotion(false)
    observer = stubIntersectionObserver()
    vi.stubGlobal('innerHeight', WINDOW_HEIGHT)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('never hides what is on screen when the page loads', () => {
    const element = renderReveal()
    placeAt(element, 100)
    act(() => {
      observer.show(element, true)
    })
    expect(element).not.toHaveAttribute('data-reveal-at')
    expect(element).not.toHaveAttribute('data-reveal-moving')
  })

  it('waits below the screen, then arrives with its stagger', () => {
    vi.useFakeTimers()
    const element = renderReveal('focus', 220)
    expect(element).toHaveAttribute('data-reveal', 'focus')
    expect(element.style.getPropertyValue('--reveal-delay')).toBe('220ms')
    placeAt(element, 1200)
    act(() => {
      observer.show(element, false)
    })
    expect(element).toHaveAttribute('data-reveal-at', 'below')

    placeAt(element, 700)
    act(() => {
      observer.show(element, true, 0.15)
    })
    expect(element).not.toHaveAttribute('data-reveal-at')
    expect(element).toHaveAttribute('data-reveal-moving', 'in')
    act(() => {
      vi.advanceTimersByTime(1900 + 220)
    })
    expect(element).not.toHaveAttribute('data-reveal-moving')
  })

  it('stays hidden while less than 15% of it shows', () => {
    const element = renderReveal()
    placeAt(element, 1200)
    act(() => {
      observer.show(element, false)
    })
    act(() => {
      observer.show(element, true, 0.1)
    })
    expect(element).toHaveAttribute('data-reveal-at', 'below')
  })

  it('leaves downward when you scroll back up, and upward once scrolled past', () => {
    const element = renderReveal()
    placeAt(element, 100)
    act(() => {
      observer.show(element, true)
    })
    placeAt(element, 900)
    act(() => {
      observer.show(element, false)
    })
    expect(element).toHaveAttribute('data-reveal-at', 'below')
    expect(element).toHaveAttribute('data-reveal-moving', 'out')

    placeAt(element, 500)
    act(() => {
      observer.show(element, true)
    })
    placeAt(element, -400)
    act(() => {
      observer.show(element, false)
    })
    expect(element).toHaveAttribute('data-reveal-at', 'above')
  })

  it('arrives from above when a jump skipped it and you scroll back up', () => {
    const element = renderReveal()
    placeAt(element, 1200)
    act(() => {
      observer.show(element, false)
    })
    expect(element).toHaveAttribute('data-reveal-at', 'below')
    const changes = new MutationObserver(() => undefined)
    changes.observe(element, {
      attributes: true,
      attributeFilter: ['data-reveal-at'],
      attributeOldValue: true,
    })
    // Its bottom edge comes in at the top of the window.
    placeAt(element, -150)
    act(() => {
      observer.show(element, true, 0.25)
    })
    // It moved to the top (from below) before it arrived (from above).
    expect(changes.takeRecords().map((change) => change.oldValue)).toEqual(['below', 'above'])
    changes.disconnect()
    expect(element).not.toHaveAttribute('data-reveal-at')
    expect(element).toHaveAttribute('data-reveal-moving', 'in')
  })

  it('shows everything at once with reduced motion', () => {
    stubReducedMotion(true)
    const element = renderReveal()
    expect(observer.observed()).not.toContain(element)
    expect(element).not.toHaveAttribute('data-reveal-at')
  })
})
