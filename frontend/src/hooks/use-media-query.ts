import { useCallback, useSyncExternalStore } from 'react'

function mediaQueryList(query: string): MediaQueryList | null {
  return typeof window.matchMedia === 'function' ? window.matchMedia(query) : null
}

/** Whether `query` matches now. False where the browser can't tell (no matchMedia, as in jsdom). */
export function matchesMediaQuery(query: string): boolean {
  return mediaQueryList(query)?.matches ?? false
}

function subscribeTo(query: string, onChange: () => void): () => void {
  const list = mediaQueryList(query)
  if (!list) return () => undefined
  list.addEventListener('change', onChange)
  return () => {
    list.removeEventListener('change', onChange)
  }
}

/**
 * Whether a CSS media query matches, kept current while the page is open. Without matchMedia
 * (jsdom, server rendering) it is false.
 */
export function useMediaQuery(query: string): boolean {
  // Stable per query, so useSyncExternalStore doesn't resubscribe on every render.
  const subscribe = useCallback((onChange: () => void) => subscribeTo(query, onChange), [query])
  return useSyncExternalStore(subscribe, () => matchesMediaQuery(query), () => false)
}
