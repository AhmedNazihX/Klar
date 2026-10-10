import { useEffect, type RefObject } from 'react'

import { usePrefersReducedMotion } from './use-prefers-reduced-motion'

/** How much of an element must show before it arrives (the system's Reveal). */
export const REVEAL_THRESHOLD = 0.15
// How long the entrance (1 s focus plus the element's stagger) and the exit keep their transition.
const ENTER_MS = 1900
const EXIT_MS = 700

/** Where a hidden element waits: below the screen, or above it after you scrolled past. */
export type RevealSide = 'below' | 'above'

/** The side of the screen an element is on: below or above the middle of the window. */
function sideOf(element: Element): RevealSide {
  const box = element.getBoundingClientRect()
  return box.top + box.height / 2 > window.innerHeight / 2 ? 'below' : 'above'
}

/**
 * Watches `ref` and moves it in as it scrolls into view and out in reverse as it leaves
 * (components.md › Reveal). What is on screen when the page loads is never hidden, and nothing
 * moves with reduced motion or without IntersectionObserver. The state lives in data attributes
 * (`data-reveal-at`, `data-reveal-moving`) that site-motion.css styles, outside React's render.
 */
export function useReveal(ref: RefObject<HTMLElement | null>, delayMs = 0): void {
  const isReducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    const element = ref.current
    if (!element || isReducedMotion || typeof IntersectionObserver === 'undefined') return
    let isFirst = true
    let timer: number | undefined

    function settleAfter(target: HTMLElement, ms: number): void {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => {
        delete target.dataset.revealMoving
      }, ms)
    }

    function enter(target: HTMLElement): void {
      // A section skipped in a jump arrives from the side it is really on.
      const from = sideOf(target)
      if (target.dataset.revealAt !== from) {
        delete target.dataset.revealMoving
        target.dataset.revealAt = from
        target.getBoundingClientRect() // Apply the new start before the transition begins.
      }
      target.dataset.revealMoving = 'in'
      delete target.dataset.revealAt
      settleAfter(target, ENTER_MS + delayMs)
    }

    function leave(target: HTMLElement): void {
      target.dataset.revealMoving = 'out'
      target.dataset.revealAt = sideOf(target)
      settleAfter(target, EXIT_MS)
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const target = entry.target as HTMLElement
          const isHidden = target.dataset.revealAt !== undefined
          if (isFirst) {
            isFirst = false
            if (!entry.isIntersecting) target.dataset.revealAt = sideOf(target)
            continue
          }
          if (entry.isIntersecting && entry.intersectionRatio >= REVEAL_THRESHOLD) {
            if (isHidden) enter(target)
          } else if (!entry.isIntersecting && !isHidden) {
            leave(target)
          }
        }
      },
      { threshold: [0, REVEAL_THRESHOLD] },
    )
    observer.observe(element)
    return () => {
      observer.disconnect()
      window.clearTimeout(timer)
      delete element.dataset.revealAt
      delete element.dataset.revealMoving
    }
  }, [ref, isReducedMotion, delayMs])
}
