import { useSyncExternalStore } from 'react'

function subscribe(onChange: () => void): () => void {
  window.addEventListener('scroll', onChange, { passive: true })
  return () => {
    window.removeEventListener('scroll', onChange)
  }
}

/** True once the window has scrolled more than `thresholdPx` down, kept current while it scrolls. */
export function useScrolled(thresholdPx: number): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.scrollY > thresholdPx,
    () => false,
  )
}
