import { useEffect, useState } from 'react'

import { usePrefersReducedMotion } from './use-prefers-reduced-motion'

/** The app's load motion clears after 3.5 s, so it never fights hover (README › Motion › App screens). */
export const LOAD_MOTION_MS = 3500

/**
 * True while a screen's load motion runs: from the moment `screenKey` changes (a new screen opens)
 * until LOAD_MOTION_MS later. Always false with reduced motion. The panels' order and their 55 ms
 * steps are in index.css › app-load.
 */
export function useLoadMotion(screenKey: string): boolean {
  const isReducedMotion = usePrefersReducedMotion()
  // The screen whose motion has finished; the motion runs while it differs from the current one.
  const [settledKey, setSettledKey] = useState<string | null>(null)

  useEffect(() => {
    if (isReducedMotion) return
    const timer = window.setTimeout(() => {
      setSettledKey(screenKey)
    }, LOAD_MOTION_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [screenKey, isReducedMotion])

  return !isReducedMotion && settledKey !== screenKey
}
