import { useEffect, useState } from 'react'

import { usePrefersReducedMotion } from './use-prefers-reduced-motion'

/** The app's load motion clears after 3.5 s, so it never fights hover (README › Motion › App screens). */
export const LOAD_MOTION_MS = 3500

export type LoadMotion = {
  /** The frame's own parts (top bar, notices) settle in: once, when the app opens. */
  isFrameEntering: boolean
  /** The screen's panels settle in: when the app opens and again on every new screen. */
  isScreenEntering: boolean
}

/**
 * Which load motion runs now, each for LOAD_MOTION_MS. Every change of `screenKey` (a navigation)
 * starts the screen's motion again, even back to a screen seen before. Nothing runs with reduced
 * motion. The panels' order and their 55 ms steps are in index.css › app-load.
 */
export function useLoadMotion(screenKey: string): LoadMotion {
  const isReducedMotion = usePrefersReducedMotion()
  // Each navigation is a new run, counted rather than keyed, so A → B → A replays on A.
  const [entry, setEntry] = useState({ key: screenKey, run: 0 })
  if (entry.key !== screenKey) setEntry({ key: screenKey, run: entry.run + 1 })
  const [settledRun, setSettledRun] = useState(-1)
  const [isFrameSettled, setFrameSettled] = useState(false)

  useEffect(() => {
    if (isReducedMotion) return
    const timer = window.setTimeout(() => {
      setFrameSettled(true)
    }, LOAD_MOTION_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [isReducedMotion])

  useEffect(() => {
    if (isReducedMotion) return
    const timer = window.setTimeout(() => {
      setSettledRun(entry.run)
    }, LOAD_MOTION_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [entry.run, isReducedMotion])

  return {
    isFrameEntering: !isReducedMotion && !isFrameSettled,
    isScreenEntering: !isReducedMotion && settledRun !== entry.run,
  }
}
