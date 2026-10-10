import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { stubIntersectionObserver } from '@/test/intersection-observer'
import { stubReducedMotion } from '@/test/reduced-motion'

import { Typewriter } from './Typewriter'

const LINES = [
  { id: 'title', content: 'classify_system → result' },
  { id: 'open', content: '{' },
  { id: 'class', content: '"risk_class": "high_risk"', indent: true },
  { id: 'close', content: '}' },
]

function renderPanel(): HTMLElement {
  render(<Typewriter label="Example result" lines={LINES} />)
  return screen.getByRole('region', { name: 'Example result' })
}

function lineVars(line: Element | undefined): Record<string, string> {
  const style = (line as HTMLElement | undefined)?.style
  return {
    n: style?.getPropertyValue('--n') ?? '',
    t: style?.getPropertyValue('--t') ?? '',
    dur: style?.getPropertyValue('--dur') ?? '',
  }
}

describe('Typewriter', () => {
  let observer: ReturnType<typeof stubIntersectionObserver>

  beforeEach(() => {
    stubReducedMotion(false)
    observer = stubIntersectionObserver()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows every line complete and focusable for scrolling', () => {
    const panel = renderPanel()
    expect(panel).toHaveTextContent('classify_system → result{"risk_class": "high_risk"}')
    expect(panel).toHaveAttribute('tabindex', '0')
    expect(panel.children[2]).toHaveClass('pl-5')
  })

  it('stays complete when it is on screen at load', () => {
    const panel = renderPanel()
    act(() => {
      observer.show(panel, true)
    })
    expect(panel).not.toHaveAttribute('data-typing')
  })

  it('types 11 ms a character with 70 ms between lines when it scrolls into view', () => {
    const panel = renderPanel()
    act(() => {
      observer.show(panel, false)
    })
    act(() => {
      observer.show(panel, true, 0.5)
    })
    expect(panel).toHaveAttribute('data-typing', 'true')
    const lines = Array.from(panel.children)
    // The title (24 characters) shows at 300 ms; "{" types after it and a 70 ms pause.
    expect(lineVars(lines[0])).toEqual({ n: '24', t: '300ms', dur: '264ms' })
    expect(lineVars(lines[1])).toEqual({ n: '1', t: `${300 + 24 * 11 + 70}ms`, dur: '11ms' })
    expect(lineVars(lines[2])).toEqual({
      n: '25',
      t: `${300 + 24 * 11 + 70 + 11 + 70}ms`,
      dur: `${25 * 11}ms`,
    })
    expect(lines[3]).toHaveAttribute('data-last')
    expect(lines[2]).not.toHaveAttribute('data-last')
  })

  it('types again each time it comes back', () => {
    const panel = renderPanel()
    act(() => {
      observer.show(panel, false)
    })
    act(() => {
      observer.show(panel, true)
    })
    act(() => {
      observer.show(panel, false)
    })
    expect(panel).not.toHaveAttribute('data-typing')
    act(() => {
      observer.show(panel, true)
    })
    expect(panel).toHaveAttribute('data-typing', 'true')
  })

  it('never types with reduced motion', () => {
    stubReducedMotion(true)
    const panel = renderPanel()
    expect(observer.observed()).toEqual([])
    expect(panel).not.toHaveAttribute('data-typing')
  })
})
