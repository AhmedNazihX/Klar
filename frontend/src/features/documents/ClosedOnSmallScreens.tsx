import { useId, useState, type JSX, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Tailwind classes per width the list opens from, written out whole so Tailwind sees them. */
const OPEN_FROM = {
  lg: { toggle: 'lg:hidden', closed: 'hidden lg:flex' },
  xl: { toggle: 'xl:hidden', closed: 'hidden xl:flex' },
} as const

/** What the list inside gets: its id (the toggle controls it), its display class, and `close`. */
export type ClosedListProps = { id: string; className: string; close: () => void }

/**
 * A list a phone or tablet shows closed, behind a toggle ("Documents (6)"), so the page opens on
 * the document rather than on the list; from `openFrom` the toggle is gone and the list always
 * shows. The list stays where it is in the reading order: only its display changes.
 */
export function ClosedOnSmallScreens({
  label,
  openFrom,
  children,
}: {
  label: string
  openFrom: keyof typeof OPEN_FROM
  children: (list: ClosedListProps) => ReactNode
}): JSX.Element {
  const id = useId()
  const [isOpen, setIsOpen] = useState(false)
  const classes = OPEN_FROM[openFrom]
  return (
    <>
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={id}
        onClick={() => {
          setIsOpen((previous) => !previous)
        }}
        className={cn(
          'flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-card-small border-0 bg-transparent px-2 text-left text-label font-medium text-ink hover:bg-white/45',
          classes.toggle,
        )}
      >
        {label}
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          className={cn('size-4 shrink-0 text-slate', isOpen && 'rotate-180')}
        >
          <path
            d="M4 6l4 4 4-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {children({
        id,
        className: isOpen ? 'flex' : classes.closed,
        close: () => {
          setIsOpen(false)
        },
      })}
    </>
  )
}
