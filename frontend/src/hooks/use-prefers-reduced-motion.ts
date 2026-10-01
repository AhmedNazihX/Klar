import { useSyncExternalStore } from 'react'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function mediaQuery(): MediaQueryList | null {
  return typeof window.matchMedia === 'function' ? window.matchMedia(REDUCED_MOTION_QUERY) : null
}

/** True when the visitor asked for reduced motion. Read it where motion is started from script. */
export function prefersReducedMotion(): boolean {
  return mediaQuery()?.matches ?? false
}

function subscribe(onChange: () => void): () => void {
  const query = mediaQuery()
  if (!query) return () => undefined
  query.addEventListener('change', onChange)
  return () => {
    query.removeEventListener('change', onChange)
  }
}

/**
 * The reduced-motion preference, kept current while the page is open. CSS already turns every
 * animation and transition off (index.css › reduced-motion); this is for motion driven from script,
 * such as the segmented control's liquid pill.
 */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, prefersReducedMotion, () => false)
}
