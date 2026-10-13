import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useId, type JSX, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { LawDate } from '@/components/LawDate'
import { RiskPill } from '@/components/RiskPill'
import { longDate, monthsUntil } from '@/features/classify/dates'
import { provisionName } from '@/features/classify/provision-names'
import { toolName } from '@/features/classify/result-text'
import type { CheckedTool } from '@/features/inventory/tool-facts'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'
import type { DutyTick } from '@/lib/duty-progress'
import { riskClassOf } from '@/lib/risk-class'

import {
  dutiesProgress,
  ticksOn,
  type DateSection,
  type SectionCategory,
  type ToolDuties,
} from './obligation-list'
import { ToolDutiesCard, type TickHandler } from './ToolDutiesCard'

/** "In 14 months" while the date is ahead, "Already applies" once it has come. */
function whenTag(t: TFunction, isoDate: string, today: Date): string {
  const months = monthsUntil(isoDate, today)
  return months > 0
    ? t('obligations.section.inMonths', { count: months })
    : t('obligations.section.alreadyApplies')
}

type Heading = { title: ReactNode; tag?: ReactNode; note?: ReactNode }

/** The line beside a dated section's heading: what its duties are ("Transparency, Art. 50"). */
function categoryNote(
  t: TFunction,
  category: SectionCategory | null,
  language: Language,
): string | undefined {
  switch (category?.kind) {
    case 'transparency':
      return t('obligations.section.transparency')
    case 'article':
      return provisionName(category.article, language)
    case 'other':
      return t('obligations.section.other')
    case undefined:
      return undefined
  }
}

/** "In force since …" or "From …", or with what the section holds in front: "Art. 6(4) from
 *  2 December 2027". */
function datedTitle(
  t: TFunction,
  section: Extract<DateSection, { kind: 'since' | 'from' }>,
  language: Language,
  what: string | null,
): ReactNode {
  const date = longDate(section.date, language)
  if (section.kind === 'since') {
    return what
      ? t('obligations.section.sinceWhat', { what, date })
      : t('obligations.section.since', { date })
  }
  return (
    <Trans
      i18nKey={what ? 'obligations.section.fromWhat' : 'obligations.section.from'}
      values={what ? { what } : undefined}
      components={{ date: <span>{date}</span> }}
    />
  )
}

function sectionHeading(
  t: TFunction,
  section: DateSection,
  language: Language,
  today: Date,
): Heading {
  switch (section.kind) {
    case 'stop':
      return {
        title: t('obligations.section.stop'),
        tag: <RiskPill kind="prohibited" />,
        note: t('obligations.section.stopNote'),
      }
    case 'since':
    case 'from': {
      const what = categoryNote(t, section.category, language)
      // Beside a route section of the same date, the title names what the section holds, so
      // the two never read "From 2 December 2027" twice; the line beside it then says no more.
      const named = section.hasRouteTwin && what ? what : null
      return {
        title: datedTitle(t, section, language, named),
        tag:
          section.kind === 'since'
            ? t('obligations.section.inForce')
            : whenTag(t, section.date, today),
        note: named ? undefined : what,
      }
    }
    case 'route':
      // The route's dates follow the law version switch (decision 026 item 11).
      return {
        title: (
          <Trans
            i18nKey="obligations.section.from"
            components={{
              date: (
                <LawDate
                  amended={longDate(section.amended, language)}
                  original={longDate(section.original, language)}
                />
              ),
            }}
          />
        ),
        tag: (
          <LawDate
            amended={whenTag(t, section.amended, today)}
            original={whenTag(t, section.original, today)}
          />
        ),
        note: t(`obligations.section.route.${section.route}`),
      }
    case 'afterChange':
      return {
        title: t('result.legacy.afterChange'),
        note: provisionName('art:111:2', language),
      }
  }
}

function sectionKey(section: DateSection): string {
  switch (section.kind) {
    case 'stop':
    case 'afterChange':
      return section.kind
    case 'route':
      return `route:${section.route}:${section.amended}`
    case 'since':
    case 'from':
      return `${section.kind}:${section.date}`
  }
}

function SectionFrame({
  heading,
  children,
}: {
  heading: Heading
  children: ReactNode
}): JSX.Element {
  const headingId = useId()
  const noteId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      aria-describedby={heading.note ? noteId : undefined}
      className="flex flex-col gap-4 px-6 py-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1.5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id={headingId} className="m-0 text-heading-small text-ink">
            {heading.title}
          </h2>
          {heading.tag && (
            <span className="text-caption font-semibold text-ink-2">{heading.tag}</span>
          )}
        </div>
        {heading.note && (
          <span id={noteId} className="text-caption text-slate">
            {heading.note}
          </span>
        )}
      </div>
      {children}
    </GlassPanel>
  )
}

/** The cards of a section, each tool with its ticks and its progress over the duties the card
 *  lists (the artboard's "1 of 7 done" beside "Show all 7 duties"). */
export function ToolCards({
  entries,
  ticks,
  onTick,
  today,
}: {
  entries: readonly ToolDuties[]
  ticks: readonly DutyTick[]
  onTick: TickHandler
  today: Date
}): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      {entries.map(({ tool, duties }) => (
        <ToolDutiesCard
          key={tool.toolId}
          tool={tool}
          duties={duties}
          progress={dutiesProgress(tool.toolId, duties, ticks)}
          done={ticksOn(ticks, tool.toolId)}
          onTick={onTick}
          today={today}
        />
      ))}
    </div>
  )
}

/** By date: one panel per section (Stop now, In force since …, From …, Only after a significant
 *  change), each with its tools' duties. */
export function DateSections({
  sections,
  ticks,
  onTick,
  today,
}: {
  sections: readonly DateSection[]
  ticks: readonly DutyTick[]
  onTick: TickHandler
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  return (
    <>
      {sections.map((section) => (
        <SectionFrame
          key={sectionKey(section)}
          heading={sectionHeading(t, section, language, today)}
        >
          <ToolCards entries={section.tools} ticks={ticks} onTick={onTick} today={today} />
        </SectionFrame>
      ))}
    </>
  )
}

/** By tool: one panel per tool with every duty it has; a tool without any says so. */
export function ToolSections({
  entries,
  ticks,
  onTick,
  today,
}: {
  entries: readonly ToolDuties[]
  ticks: readonly DutyTick[]
  onTick: TickHandler
  today: Date
}): JSX.Element {
  return (
    <GlassPanel className="flex flex-col gap-3 px-6 py-6">
      <ToolCards entries={entries} ticks={ticks} onTick={onTick} today={today} />
    </GlassPanel>
  )
}

/** "No specific duties": minimal-risk and out-of-scope tools, each linking to its result. */
export function NoDutiesSection({ tools }: { tools: readonly CheckedTool[] }): JSX.Element {
  const { t } = useTranslation()
  return (
    <SectionFrame
      heading={{ title: t('obligations.section.none'), note: t('obligations.section.noneNote') }}
    >
      <ul className="m-0 flex list-none flex-wrap gap-2.5 p-0">
        {tools.map((tool) => (
          <li key={tool.toolId}>
            <Link
              to="/app/inventory/$toolId"
              params={{ toolId: tool.toolId }}
              className="flex min-h-11 items-center gap-2.5 rounded-item px-3.5 py-2 text-body-small font-medium text-ink no-underline glass-thin hover:underline md:min-h-0"
            >
              {toolName(t, tool.name)}
              <RiskPill kind={riskClassOf(tool.result)} />
            </Link>
          </li>
        ))}
      </ul>
    </SectionFrame>
  )
}
