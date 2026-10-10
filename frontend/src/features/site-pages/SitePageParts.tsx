import { useId, type JSX, type ReactNode } from 'react'

import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { Reveal } from '@/components/Reveal'
import { cn } from '@/lib/utils'

// The building blocks the four site pages share (artboards Method, Privacy, Impressum, Contact):
// the page's heading and lead, the template note, glass sections that arrive on scroll, and the
// label-and-text rows inside them.

/**
 * The page's one h1 (56 px from md up, as drawn) and the muted lead under it. A long German title
 * ("Datenschutzerklärung") hyphenates, or breaks, rather than overflow a 360 px phone.
 */
export function PageIntro({
  title,
  lead,
  titleLang,
}: {
  title: string
  lead: ReactNode
  /** The title's language, when it differs from the page's (the Impressum on the English site). */
  titleLang?: string
}): JSX.Element {
  return (
    <div className="flex max-w-[820px] flex-col gap-4.5">
      <h1
        lang={titleLang}
        className="m-0 text-[36px] leading-[1.04] font-semibold tracking-[-0.04em] [overflow-wrap:anywhere] hyphens-auto text-ink md:text-[56px]"
      >
        {title}
      </h1>
      <p className="m-0 text-body-large text-slate md:text-[19px]">{lead}</p>
    </div>
  )
}

/** The note that a page is a template whose bracketed fields must be filled in before launch. */
export function TemplateNote({ children }: { children: ReactNode }): JSX.Element {
  return (
    <GlassPanel
      tone="thin"
      padded={false}
      role="note"
      className="flex items-start gap-2.5 rounded-[18px] px-4.5 py-3.5 text-body-small text-ink-2"
    >
      <Icon name="info" size={18} className="mt-0.5 shrink-0 text-lens-blue" />
      <span>{children}</span>
    </GlassPanel>
  )
}

/** A glass section with its h2, arriving as it scrolls into view. No glint: it is for reading. */
export function InfoSection({
  title,
  children,
  lang,
  className,
}: {
  title: string
  children: ReactNode
  /** The section's language, when it differs from the page's (the Impressum's German body). */
  lang?: string
  className?: string
}): JSX.Element {
  const headingId = useId()
  return (
    <Reveal>
      <GlassPanel
        as="section"
        radius="panel"
        aria-labelledby={headingId}
        lang={lang}
        className={cn('flex flex-col gap-4 md:px-10 md:py-9', className)}
      >
        <h2
          id={headingId}
          className="m-0 text-[22px] leading-[1.2] font-semibold tracking-[-0.025em] text-ink md:text-[26px]"
        >
          {title}
        </h2>
        {children}
      </GlassPanel>
    </Reveal>
  )
}

/** A paragraph of running text inside an InfoSection. */
export function InfoText({ children }: { children: ReactNode }): JSX.Element {
  return <p className="m-0 max-w-[820px] text-body leading-[1.65] text-ink-2">{children}</p>
}

export type InfoRow = { key: string; label: ReactNode; text: ReactNode }

/**
 * Label-and-text rows under hairlines, as a description list: the label in a 260 px column from
 * md up, stacked above its text on a phone.
 */
export function InfoRows({ rows }: { rows: readonly InfoRow[] }): JSX.Element {
  return (
    <dl className="m-0 flex flex-col">
      {rows.map((row) => (
        <div
          key={row.key}
          className="grid grid-cols-1 gap-1 border-t border-hairline py-3.5 text-body-small md:grid-cols-[260px_minmax(0,1fr)] md:gap-6"
        >
          <dt className="font-semibold text-ink">{row.label}</dt>
          <dd className="m-0 min-w-0 text-ink-2">{row.text}</dd>
        </div>
      ))}
    </dl>
  )
}
