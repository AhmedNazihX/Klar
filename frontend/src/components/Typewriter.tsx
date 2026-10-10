import { useEffect, useRef, type JSX, type ReactNode } from 'react'

import { REVEAL_THRESHOLD } from '@/hooks/use-reveal'
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion'
import { cn } from '@/lib/utils'

/** Milliseconds per character (the type-char token) and between lines. */
export const TYPE_CHAR_MS = 11
export const TYPE_LINE_PAUSE_MS = 70
// The first line shows at once; the second starts typing after this.
const START_DELAY_MS = 300
// How long the caret keeps blinking at the end before the typing state clears.
const CARET_LINGER_MS = 2200

/** One line; `indent` moves it in one step (20 px) without counting as typed characters. */
export type TypewriterLine = { id: string; content: ReactNode; indent?: boolean }

/** When each line after the first starts and how long it types, from its length in characters. */
function typingSchedule(
  lengths: readonly number[],
  speed = TYPE_CHAR_MS,
  pause = TYPE_LINE_PAUSE_MS,
): { startMs: number; durationMs: number }[] {
  let at = START_DELAY_MS
  return lengths.map((length) => {
    const line = { startMs: at, durationMs: Math.max(1, length * speed) }
    at += length * speed + pause
    return line
  })
}

/** Starts the typing: each line's length and timing go into CSS variables (site-motion.css). */
function type(panel: HTMLElement): number {
  const lines = Array.from(panel.children) as HTMLElement[]
  const schedule = typingSchedule(lines.map((line) => line.textContent.length))
  lines.forEach((line, index) => {
    const { startMs, durationMs } = schedule[index] ?? { startMs: 0, durationMs: 1 }
    line.style.setProperty('--n', String(line.textContent.length))
    line.style.setProperty('--t', `${startMs}ms`)
    line.style.setProperty('--dur', `${durationMs}ms`)
    line.toggleAttribute('data-last', index === lines.length - 1)
  })
  delete panel.dataset.typing
  panel.getBoundingClientRect() // Restart the animation when it types again.
  panel.dataset.typing = 'true'
  const last = schedule.at(-1)
  return last ? last.startMs + last.durationMs : 0
}

/**
 * A code example that types itself out like a streaming answer (components.md › Typewriter): it
 * starts when it scrolls into view and types again each time it comes back. Once per page, on
 * glass-dark. What is on screen at load, and everything under reduced motion, shows complete.
 */
export function Typewriter({
  lines,
  label,
  className,
}: {
  lines: readonly TypewriterLine[]
  label: string
  className?: string
}): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)
  const isReducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    const panel = ref.current
    if (!panel || isReducedMotion || typeof IntersectionObserver === 'undefined') return
    let isFirst = true
    let isOut = false
    let timer: number | undefined
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (isFirst) {
            isFirst = false
            isOut = !entry.isIntersecting
          } else if (entry.isIntersecting && entry.intersectionRatio >= REVEAL_THRESHOLD) {
            if (!isOut) continue
            isOut = false
            const typingMs = type(panel)
            window.clearTimeout(timer)
            timer = window.setTimeout(() => {
              delete panel.dataset.typing
            }, typingMs + CARET_LINGER_MS)
          } else if (!entry.isIntersecting) {
            isOut = true
            window.clearTimeout(timer)
            delete panel.dataset.typing
          }
        }
      },
      { threshold: [0, REVEAL_THRESHOLD] },
    )
    observer.observe(panel)
    return () => {
      observer.disconnect()
      window.clearTimeout(timer)
      delete panel.dataset.typing
    }
  }, [isReducedMotion])

  return (
    // A long line scrolls inside the panel on a phone, so the panel takes keyboard focus.
    <div
      ref={ref}
      role="region"
      aria-label={label}
      tabIndex={0}
      className={cn('typewriter overflow-x-auto font-mono text-code', className)}
    >
      {lines.map((line) => (
        <div key={line.id} className={line.indent ? 'pl-5' : undefined}>
          {line.content}
        </div>
      ))}
    </div>
  )
}
