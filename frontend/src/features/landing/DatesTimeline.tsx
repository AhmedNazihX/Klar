import { Fragment, type CSSProperties, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Reveal } from '@/components/Reveal'
import { LANGUAGE_LOCALES, type Language } from '@/i18n'
import { cn } from '@/lib/utils'

import { SectionTitle } from './SectionTitle'
import { hasPassed, passedCount, TIMELINE_DATES, todayPosition } from './timeline'

// When each date's dot appears after the line starts drawing (the artboard's timing).
const DOT_DELAYS_MS = [300, 700, 900, 1100] as const

/** A point on the line, `position` dates from the first: the columns are 24 px apart. */
function lineOffset(position: number): string {
  return `calc(${position} * ((100% - 72px) / 4 + 24px))`
}

function TodayChip({
  label,
  className,
  style,
}: {
  label: string
  className?: string
  style?: CSSProperties
}): JSX.Element {
  return (
    <span
      style={style}
      className={cn(
        'rounded-pill px-2 py-[3px] text-micro font-semibold whitespace-nowrap text-ink glass-thin',
        className,
      )}
    >
      {label}
    </span>
  )
}

/**
 * "The dates moved in July 2026." (components.md › Timeline): the four application dates on a line
 * with Today placed at the real date; the Lens blue line draws to it as the panel arrives. Dates
 * that apply already are filled dots, dates to come are rings, and each says so in words. On a
 * phone the dates stack, with Today between the last date passed and the next.
 */
export function DatesTimeline({ today = new Date() }: { today?: Date }): JSX.Element {
  const { t, i18n } = useTranslation()
  const language: Language = i18n.resolvedLanguage === 'de' ? 'de' : 'en'
  const format = new Intl.DateTimeFormat(LANGUAGE_LOCALES[language], {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
  const isoDates = TIMELINE_DATES.map(({ isoDate }) => isoDate)
  const todayAt = lineOffset(todayPosition(isoDates, today))
  const todayIndex = passedCount(isoDates, today)
  const todayLabel = t('landing.dates.today')

  return (
    <section aria-labelledby="dates" className="mt-24">
      <Reveal className="flex flex-col gap-9 rounded-feature p-7 glass md:px-12 md:py-11">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end md:gap-10">
          <SectionTitle id="dates" size="page">
            {t('landing.dates.title')}
          </SectionTitle>
          <p className="max-w-[520px] text-body text-slate">{t('landing.dates.lead')}</p>
        </div>
        <div className="relative md:pt-7">
          <div
            aria-hidden="true"
            className="absolute inset-x-0 top-[7px] hidden h-0.5 bg-ink/18 md:block"
          >
            <div
              data-testid="timeline-fill"
              className="timeline-fill absolute inset-y-0 left-0 bg-lens-blue"
              style={{ width: todayAt }}
            />
          </div>
          <TodayChip
            label={todayLabel}
            className="timeline-today absolute -top-3.5 hidden -translate-x-1/2 md:block"
            style={{ left: todayAt }}
          />
          <ol className="m-0 grid list-none grid-cols-1 gap-6 p-0 md:grid-cols-4">
            {TIMELINE_DATES.map(({ id, isoDate }, index) => {
              const isPast = hasPassed(isoDate, today)
              return (
                <Fragment key={id}>
                  {index === todayIndex && (
                    <li className="md:hidden">
                      <TodayChip label={todayLabel} />
                    </li>
                  )}
                  <li
                    data-past={isPast ? 'true' : undefined}
                    className="relative flex flex-col gap-2 pl-7 md:pl-0"
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        'timeline-dot absolute top-1 left-0 size-4 rounded-full md:-top-7',
                        isPast
                          ? 'bg-lens-blue shadow-[0_0_0_4px_rgb(45_75_224/0.2)]'
                          : 'bg-white shadow-[inset_0_0_0_2px_var(--color-lens-blue)]',
                      )}
                      style={{ '--dot-delay': `${DOT_DELAYS_MS[index] ?? 0}ms` } as CSSProperties}
                    />
                    <span className="text-heading-panel">{format.format(new Date(isoDate))}</span>
                    <span className="sr-only">
                      {isPast ? t('landing.dates.past') : t('landing.dates.upcoming')}
                    </span>
                    <span className="text-body-small text-slate">
                      {t(`landing.dates.items.${id}`)}
                    </span>
                  </li>
                </Fragment>
              )
            })}
            {todayIndex === TIMELINE_DATES.length && (
              <li className="md:hidden">
                <TodayChip label={todayLabel} />
              </li>
            )}
          </ol>
        </div>
      </Reveal>
    </section>
  )
}
