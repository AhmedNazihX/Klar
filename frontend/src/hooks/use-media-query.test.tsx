import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useMediaQuery } from './use-media-query'

const QUERY = '(width < 48rem)'

/** A matchMedia whose answer the test changes, firing `change` like a resized window would. */
function stubChangingMatchMedia(initial: boolean): {
  setMatches: (next: boolean) => void
  listenerCount: () => number
} {
  let matches = initial
  const listeners = new Set<() => void>()
  vi.stubGlobal(
    'matchMedia',
    (query: string): MediaQueryList =>
      ({
        get matches() {
          return matches
        },
        media: query,
        addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
      }) as unknown as MediaQueryList,
  )
  return {
    setMatches: (next) => {
      matches = next
      listeners.forEach((listener) => listener())
    },
    listenerCount: () => listeners.size,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useMediaQuery', () => {
  it('follows the query as it starts and stops matching, and unsubscribes on unmount', () => {
    const media = stubChangingMatchMedia(false)
    const { result, unmount } = renderHook(() => useMediaQuery(QUERY))
    expect(result.current).toBe(false)

    act(() => media.setMatches(true))
    expect(result.current).toBe(true)

    act(() => media.setMatches(false))
    expect(result.current).toBe(false)

    unmount()
    expect(media.listenerCount()).toBe(0)
  })

  it('is false where the browser cannot tell (no matchMedia)', () => {
    vi.stubGlobal('matchMedia', undefined)
    expect(renderHook(() => useMediaQuery(QUERY)).result.current).toBe(false)
  })
})
