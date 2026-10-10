import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Icon } from './Icon'
import type { PillKind } from './pill-kinds'

type RiskClassKind = Exclude<PillKind, 'legally_ambiguous' | 'needs_more_information'>

const DOT: Record<RiskClassKind, string> = {
  prohibited: 'bg-risk-prohibited-dot shadow-[0_0_0_5px_var(--color-risk-prohibited-tint)]',
  high_risk: 'bg-risk-high-dot shadow-[0_0_0_5px_rgb(229_122_30/0.18)]',
  limited_risk: 'bg-risk-limited-dot shadow-[0_0_0_5px_var(--color-risk-limited-tint)]',
  minimal_risk: 'bg-risk-minimal-dot shadow-[0_0_0_5px_var(--color-risk-minimal-tint)]',
  out_of_scope: 'bg-risk-out-dot shadow-[0_0_0_5px_var(--color-risk-out-tint)]',
}

/** The warm glass of a High-risk result (artboard `Result`) and the red-tinted glass of a
 *  Prohibited one (artboard `ResultProhibited`); other classes stay plain glass. */
const TINTS: Partial<Record<RiskClassKind, string>> = {
  high_risk: 'linear-gradient(150deg, rgb(255 255 255 / 0.8), rgb(255 232 212 / 0.5))',
  prohibited: 'linear-gradient(150deg, rgb(255 255 255 / 0.8), rgb(255 226 226 / 0.5))',
}

export type ResultSummaryProps = {
  riskClass: RiskClassKind
  /** The status pills beside the class: Decided, or Assumed with the uncertain status. */
  status: ReactNode
  /** Role and basis: "You're the deployer. The tool is listed in Annex III 4(a): …" */
  statement: ReactNode
  /** A line under the statement, e.g. where Klar paused. */
  statusLine?: ReactNode
  dutiesFromLabel?: ReactNode
  dutiesFrom?: ReactNode
  dutiesNote?: ReactNode
  /** The legal-review line (High-risk, Prohibited and ambiguous results). */
  legalReview?: ReactNode
  /** Notices under the date, e.g. the Art. 111(2) sentence. */
  children?: ReactNode
}

/**
 * The top of every result, in an order that never changes: the class in Lexend with its dot and
 * status, who you are and why, then the date duties apply from (or, on a Prohibited result, the
 * date it has been banned since). High-risk and Prohibited results get their tinted glass.
 */
export function ResultSummary({
  riskClass,
  status,
  statement,
  statusLine,
  dutiesFromLabel,
  dutiesFrom,
  dutiesNote,
  legalReview,
  children,
}: ResultSummaryProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <section
      aria-label={t('result.label')}
      data-risk-class={riskClass}
      className="flex min-w-0 flex-col gap-5 rounded-panel px-6 py-6 glass md:px-8.5 md:py-7.5"
      // The warm tint replaces the glass fill (the glass utility's own background would win
      // over a background class).
      style={TINTS[riskClass] ? { background: TINTS[riskClass] } : undefined}
    >
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-col gap-3.5">
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
            <span
              aria-hidden="true"
              className={cn('size-4 shrink-0 rounded-full', DOT[riskClass])}
            />
            <span className="verdict font-brand text-[44px] leading-[1.05] font-semibold tracking-[-0.03em] text-ink md:text-verdict">
              {t(`pill.${riskClass}`)}
            </span>
            <span className="flex flex-wrap items-center gap-2">{status}</span>
          </div>
          <p className="m-0 max-w-[600px] text-[19px] leading-[1.45] font-medium text-ink">
            {statement}
          </p>
          {statusLine && <p className="m-0 max-w-[600px] text-body text-ink-2">{statusLine}</p>}
        </div>
        {dutiesFrom && (
          <div className="flex min-w-[250px] flex-col gap-1 rounded-[22px] px-5.5 py-4.5 glass-thin">
            <span className="text-caption font-normal text-slate">{dutiesFromLabel}</span>
            <span className="text-[28px] leading-tight font-semibold tracking-[-0.02em] text-ink">
              {dutiesFrom}
            </span>
            {dutiesNote && (
              <span className="text-caption font-normal text-slate">{dutiesNote}</span>
            )}
          </div>
        )}
      </div>
      {children}
      {legalReview && (
        <p className="m-0 flex items-start gap-2.5 text-label font-normal text-ink-2">
          <Icon name="info" size={18} className="mt-px" />
          <span>{legalReview}</span>
        </p>
      )}
    </section>
  )
}
