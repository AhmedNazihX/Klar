import type { JSX } from 'react'

import { cn } from '@/lib/utils'

export type ChoiceGroupProps<T extends string> = {
  /** The group's accessible name, also shown above it. */
  label: string
  options: readonly { value: T; label: string }[]
  /** null while nothing is chosen: every profile field is optional. */
  value: T | null
  onChange: (value: T) => void
}

/**
 * Answer buttons with aria-pressed, in the segmented look (components.md: answers are buttons, not
 * a SegmentedControl, so "nothing chosen yet" is possible). They wrap on a narrow screen.
 */
export function ChoiceGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: ChoiceGroupProps<T>): JSX.Element {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <span className="text-label font-semibold text-ink">{label}</span>
      <div
        role="group"
        aria-label={label}
        className="flex flex-wrap gap-1 self-start rounded-[22px] p-[3px] glass-thin"
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={option.value === value}
            onClick={() => {
              onChange(option.value)
            }}
            className={cn(
              'h-9 cursor-pointer rounded-pill px-3.5 text-sm leading-none font-semibold whitespace-nowrap text-slate',
              'transition-colors duration-300 ease-settle hover:text-ink',
              'aria-pressed:bg-white aria-pressed:text-ink aria-pressed:shadow-segment',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}
