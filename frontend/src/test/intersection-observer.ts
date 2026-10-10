import { vi } from 'vitest'

type Observed = { element: Element; callback: IntersectionObserverCallback }

/**
 * jsdom has no IntersectionObserver. This stub records what each observer watches, so a test can
 * say when an element enters or leaves the screen (`show`). Undo it with `vi.unstubAllGlobals()`.
 */
export function stubIntersectionObserver(): {
  observed: () => Element[]
  show: (element: Element, isOnScreen: boolean, ratio?: number) => void
} {
  const watched: Observed[] = []

  class FakeIntersectionObserver {
    readonly root = null
    readonly rootMargin = '0px'
    readonly thresholds: readonly number[] = [0]
    private readonly callback: IntersectionObserverCallback

    constructor(callback: IntersectionObserverCallback) {
      this.callback = callback
    }

    observe(element: Element): void {
      watched.push({ element, callback: this.callback })
    }

    unobserve(element: Element): void {
      const index = watched.findIndex((entry) => entry.element === element)
      if (index !== -1) watched.splice(index, 1)
    }

    disconnect(): void {
      for (let index = watched.length - 1; index >= 0; index -= 1) {
        if (watched[index]?.callback === this.callback) watched.splice(index, 1)
      }
    }

    takeRecords(): IntersectionObserverEntry[] {
      return []
    }
  }

  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)

  return {
    observed: () => watched.map(({ element }) => element),
    show(element, isOnScreen, ratio = isOnScreen ? 1 : 0) {
      for (const entry of watched.filter((item) => item.element === element)) {
        const box = element.getBoundingClientRect()
        const record = {
          target: element,
          isIntersecting: isOnScreen,
          intersectionRatio: ratio,
          boundingClientRect: box,
          intersectionRect: box,
          rootBounds: null,
          time: 0,
        } as IntersectionObserverEntry
        entry.callback([record], {} as IntersectionObserver)
      }
    },
  }
}
