import { matchesMediaQuery, useMediaQuery } from './use-media-query'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

/** True when the visitor asked for reduced motion. Read it where motion is started from script. */
export function prefersReducedMotion(): boolean {
  return matchesMediaQuery(REDUCED_MOTION_QUERY)
}

/**
 * The reduced-motion preference, kept current while the page is open. CSS already turns every
 * animation and transition off (index.css › reduced-motion); this is for motion driven from script,
 * such as the segmented control's liquid pill.
 */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery(REDUCED_MOTION_QUERY)
}
