import type { TFunction } from 'i18next'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { longDate, monthsUntil } from '@/features/classify/dates'
import { toolName } from '@/features/classify/result-text'
import type { CheckedTool } from '@/features/inventory/tool-facts'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import { checklistTool, reportFailureKey, useExportChecklist } from '@/hooks/use-report-export'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'
import { LANGUAGE_LOCALES, type Language } from '@/i18n'
import type { DutyTick } from '@/lib/duty-progress'

import { nextDate, ticksOn, type NextDate, type Progress } from './obligation-list'

function startSentence(t: TFunction, next: NextDate, language: Language): string {
  const names = new Intl.ListFormat(LANGUAGE_LOCALES[language], {
    style: 'long',
    type: 'conjunction',
  }).format(next.tools.map((tool) => toolName(t, tool.name)))
  if (next.tools.length === 0) return t('obligations.next.onlyAssumed', { count: next.assumed })
  if (next.assumed === 0) return t('obligations.next.tools', { tools: names })
  return t('obligations.next.toolsAndMore', { tools: names, count: next.assumed })
}

/** "Next date": the earliest date still ahead under the law text on show, and whose duties
 *  start then. */
function NextDatePanel({
  tools,
  today,
}: {
  tools: readonly CheckedTool[]
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const next = nextDate(tools, today, useLawVersion())
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-2.5 p-6">
      <h2 id={headingId} className="m-0 text-heading-small text-ink">
        {t('obligations.next.heading')}
      </h2>
      {next ? (
        <>
          <p className="m-0 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-heading-panel text-ink">{longDate(next.date, language)}</span>
            <span className="text-caption font-semibold text-ink-2">
              {t('obligations.section.inMonths', { count: monthsUntil(next.date, today) })}
            </span>
          </p>
          <p className="m-0 text-body-small text-slate">{startSentence(t, next, language)}</p>
        </>
      ) : (
        <p className="m-0 text-body-small text-slate">{t('obligations.next.none')}</p>
      )}
    </GlassPanel>
  )
}

/** "Progress": the duties ticked off across every tool, and that Klar doesn't check the work. */
function ProgressPanel({ progress }: { progress: Progress }): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const share = progress.total > 0 ? (progress.done / progress.total) * 100 : 0
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3 p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={headingId} className="m-0 text-heading-small text-ink">
          {t('obligations.progress.heading')}
        </h2>
        <span className="text-caption font-semibold text-ink-2">
          {t('obligations.progress.done', progress)}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={t('obligations.progress.label')}
        aria-valuemin={0}
        aria-valuemax={progress.total}
        aria-valuenow={progress.done}
        className="h-2 overflow-hidden rounded-pill bg-white/50"
      >
        <div className="h-full rounded-pill bg-lens-blue" style={{ width: `${String(share)}%` }} />
      </div>
      <p className="m-0 text-body-small text-slate">{t('obligations.progress.body')}</p>
    </GlassPanel>
  )
}

/** "Take the checklist with you": every duty with its ticked state, as a PDF or Word file made
 *  by the API. One click is one request. */
function ChecklistPanel({
  tools,
  ticks,
}: {
  tools: readonly CheckedTool[]
  ticks: readonly DutyTick[]
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const download = useExportChecklist()
  const overview = useUserDataOverview()
  function save(format: 'pdf' | 'docx'): void {
    download.mutate({
      tools: tools.map((tool) => checklistTool(tool, language, ticksOn(ticks, tool.toolId))),
      language,
      format,
      company: overview.data?.profile?.companyName ?? null,
    })
  }
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3 p-6">
      <h2 id={headingId} className="m-0 text-heading-small text-ink">
        {t('obligations.export.heading')}
      </h2>
      <p className="m-0 text-body-small text-slate">{t('obligations.export.body')}</p>
      <div className="flex flex-wrap gap-2.5">
        <Button variant="ghost" disabled={download.isPending} onClick={() => save('pdf')}>
          {t('obligations.export.pdf')}
        </Button>
        <Button variant="ghost" disabled={download.isPending} onClick={() => save('docx')}>
          {t('obligations.export.word')}
        </Button>
      </div>
      {download.isPending && (
        <p role="status" className="m-0 text-caption text-slate">
          {t('obligations.export.pending')}
        </p>
      )}
      {download.isError && (
        <p role="alert" className="m-0 text-caption text-risk-prohibited">
          {t(reportFailureKey(download.error))}
        </p>
      )}
    </GlassPanel>
  )
}

/** The screen's side column: the next date, the progress and the checklist download. */
export function ObligationsAside({
  tools,
  ticks,
  progress,
  today,
}: {
  tools: readonly CheckedTool[]
  ticks: readonly DutyTick[]
  progress: Progress
  today: Date
}): JSX.Element {
  return (
    <div className="flex min-w-0 flex-col gap-5 xl:w-[340px] xl:shrink-0">
      <NextDatePanel tools={tools} today={today} />
      <ProgressPanel progress={progress} />
      <ChecklistPanel tools={tools} ticks={ticks} />
    </div>
  )
}
