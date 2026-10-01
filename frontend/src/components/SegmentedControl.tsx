import { useEffect, useLayoutEffect, useRef, useState, type JSX, type ReactNode } from 'react'

import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion'
import { cn } from '@/lib/utils'

export type SegmentOption<T extends string> = {
  value: T
  label: ReactNode
  /** The option's language, when its label is in another language than the page (EN, DE). */
  lang?: string
}

export type SegmentedControlProps<T extends string> = {
  /** Accessible name of the group, e.g. "Law version". */
  label: string
  options: readonly SegmentOption<T>[]
  value?: T
  defaultValue?: T
  onChange?: (value: T) => void
  className?: string
}

// The liquid switch: the pill first stretches to reach the new option (liquid-stretch, ease-settle),
// then draws its tail in under it (liquid-settle, ease-out). The settle starts just before the
// stretch ends, as in the system's own control, so the motion reads as one.
const STRETCH =
  'left var(--liquid-stretch) var(--ease-settle), width var(--liquid-stretch) var(--ease-settle)'
const SETTLE =
  'left var(--liquid-settle) var(--ease-out), width var(--liquid-settle) var(--ease-out)'
const SETTLE_DELAY_MS = 150

type Box = { left: number; width: number }

function boxOf(button: HTMLButtonElement | undefined): Box | null {
  return button ? { left: button.offsetLeft, width: button.offsetWidth } : null
}

function place(thumb: HTMLElement | null, box: Box | null, transition = 'none'): void {
  if (!thumb || !box) return
  thumb.style.transition = transition
  thumb.style.left = `${box.left}px`
  thumb.style.width = `${box.width}px`
}

/** A pill switch between two or three equal views (law version, language, Summary or Reviewer). */
export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  defaultValue,
  onChange,
  className,
}: SegmentedControlProps<T>): JSX.Element {
  const [ownValue, setOwnValue] = useState<T | undefined>(defaultValue ?? options[0]?.value)
  const current = value ?? ownValue
  const isReducedMotion = usePrefersReducedMotion()

  const groupRef = useRef<HTMLDivElement>(null)
  const thumbRef = useRef<HTMLSpanElement>(null)
  const buttonsRef = useRef(new Map<string, HTMLButtonElement>())
  const previousRef = useRef(current)
  const timerRef = useRef<number | undefined>(undefined)

  // Moves the pill, a DOM element outside React's state, whenever the choice changes.
  useLayoutEffect(() => {
    const buttons = buttonsRef.current
    const to = boxOf(current === undefined ? undefined : buttons.get(current))
    const from = boxOf(
      previousRef.current === undefined ? undefined : buttons.get(previousRef.current),
    )
    groupRef.current?.setAttribute('data-live', 'true')
    window.clearTimeout(timerRef.current)
    timerRef.current = undefined
    if (!from || !to || previousRef.current === current || isReducedMotion) {
      place(thumbRef.current, to)
    } else {
      const left = Math.min(from.left, to.left)
      const right = Math.max(from.left + from.width, to.left + to.width)
      place(thumbRef.current, { left, width: right - left }, STRETCH)
      timerRef.current = window.setTimeout(() => {
        timerRef.current = undefined
        // Measured now, not at the click, in case a button resized during the stretch.
        place(thumbRef.current, boxOf(buttons.get(current ?? '')), SETTLE)
      }, SETTLE_DELAY_MS)
    }
    previousRef.current = current
  }, [current, isReducedMotion])

  // A label that changes width (another language, a web font arriving) moves the buttons while the
  // choice stays the same: measure the pill again whenever any button resizes. Re-observed only
  // when the set of options changes, so a re-render never interrupts the liquid motion.
  const optionKey = options.map((option) => option.value).join('\u0000')
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      // While the pill flows to a new choice, let the settle step place it.
      if (timerRef.current !== undefined) return
      const selected = previousRef.current
      if (selected !== undefined) place(thumbRef.current, boxOf(buttonsRef.current.get(selected)))
    })
    for (const button of buttonsRef.current.values()) observer.observe(button)
    return () => {
      observer.disconnect()
    }
  }, [optionKey])

  useEffect(
    () => () => {
      window.clearTimeout(timerRef.current)
    },
    [],
  )

  function choose(next: T): void {
    if (next === current) return
    if (value === undefined) setOwnValue(next)
    onChange?.(next)
  }

  return (
    <div
      ref={groupRef}
      role="group"
      aria-label={label}
      className={cn(
        'group/seg relative inline-flex shrink-0 rounded-pill p-[3px] glass-thin',
        className,
      )}
    >
      <span
        ref={thumbRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-[3px] left-[3px] w-0 rounded-pill bg-white opacity-0 shadow-segment-thumb group-data-live/seg:opacity-100"
      />
      {options.map((option) => (
        <button
          key={option.value}
          ref={(node) => {
            if (node) buttonsRef.current.set(option.value, node)
            else buttonsRef.current.delete(option.value)
          }}
          type="button"
          lang={option.lang}
          aria-pressed={option.value === current}
          onClick={() => {
            choose(option.value)
          }}
          className="relative z-1 h-9 cursor-pointer rounded-pill px-3.5 text-sm leading-none font-semibold whitespace-nowrap text-slate transition-colors duration-300 ease-settle hover:text-ink aria-pressed:bg-white aria-pressed:text-ink aria-pressed:shadow-segment group-data-live/seg:aria-pressed:bg-transparent group-data-live/seg:aria-pressed:shadow-none"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
