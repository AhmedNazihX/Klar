import { vi } from 'vitest'

/**
 * jsdom has no matchMedia. Stub it so `(prefers-reduced-motion: reduce)` answers `isReduced`, and
 * undo it with `vi.unstubAllGlobals()`.
 */
export function stubReducedMotion(isReduced: boolean): void {
  vi.stubGlobal(
    'matchMedia',
    (query: string): MediaQueryList =>
      ({
        matches: isReduced && query.includes('prefers-reduced-motion: reduce'),
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      }) as MediaQueryList,
  )
}
