import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type JSX,
  type ReactNode,
} from 'react'

import { cn } from '@/lib/utils'

/** Tailwind classes per width the list opens from, written out whole so Tailwind sees them. */
const OPEN_FROM = {
  lg: { toggle: 'lg:hidden', closed: 'hidden lg:flex' },
  xl: { toggle: 'xl:hidden', closed: 'hidden xl:flex' },
} as const

/** The list whose toggle takes the focus as it mounts. Picking a link can change the route (from
 *  /app/documents to a document), which mounts the screen anew: the toggle that had the focus is
 *  gone with the old screen, and the focus would fall to the page's start. The old toggle names
 *  its list here as it goes, and the new one takes the focus in the same commit; whatever no new
 *  toggle takes is dropped once that commit is done. */
let focusOnMount: string | null = null

/** What the list inside gets: its id (the toggle controls it), its display class, and `close`,
 *  which closes it and gives the focus back to the toggle: a link picked in the list disappears
 *  with it, and the focus would otherwise fall to the page's start. Where the list always shows,
 *  the toggle is hidden, so the focus stays where it is. */
export type ClosedListProps = { id: string; className: string; close: () => void }

/**
 * A list a phone or tablet shows closed, behind a toggle ("Documents (6)"), so the page opens on
 * the document rather than on the list; from `openFrom` the toggle is gone and the list always
 * shows. The list stays where it is in the reading order: only its display changes.
 */
export function ClosedOnSmallScreens({
  name,
  label,
  openFrom,
  children,
}: {
  /** Which list this is, the same across screens ("documents", "sections"). */
  name: string
  label: string
  openFrom: keyof typeof OPEN_FROM
  children: (list: ClosedListProps) => ReactNode
}): JSX.Element {
  const id = useId()
  const toggleRef = useRef<HTMLButtonElement>(null)
  const [isOpen, setIsOpen] = useState(false)
  const classes = OPEN_FROM[openFrom]
  // Focus is outside React. Before the old toggle leaves the page (a layout effect's cleanup runs
  // while it is still there), it hands the focus on to the toggle of the same list on the new one.
  useLayoutEffect(() => {
    const toggle = toggleRef.current
    return () => {
      if (toggle === null || document.activeElement !== toggle) return
      focusOnMount = name
      queueMicrotask(() => {
        focusOnMount = null
      })
    }
  }, [name])
  useEffect(() => {
    if (focusOnMount !== name) return
    focusOnMount = null
    toggleRef.current?.focus()
  }, [name])
  return (
    <>
      <button
        ref={toggleRef}
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
          toggleRef.current?.focus()
        },
      })}
    </>
  )
}
