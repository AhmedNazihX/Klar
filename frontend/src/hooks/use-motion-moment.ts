import { useEffect, useState } from 'react'

import { prefersReducedMotion } from './use-prefers-reduced-motion'

/**
 * True from the first render for `durationMs`, then false for good: the length of a one-off motion
 * such as the hero's load sequence or the language pill's arrival. Never true when `isWanted` is
 * false at the first render, or with reduced motion.
 */
export function useMotionMoment(durationMs: number, isWanted = true): boolean {
  const [isMoving, setMoving] = useState(() => isWanted && !prefersReducedMotion())
  useEffect(() => {
    if (!isMoving) return
    const timer = window.setTimeout(() => {
      setMoving(false)
    }, durationMs)
    return () => {
      window.clearTimeout(timer)
    }
  }, [isMoving, durationMs])
  return isMoving
}
