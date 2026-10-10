import { Link } from '@tanstack/react-router'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { ScreenLawSwitch } from '@/components/AppTopBar'
import { buttonVariants } from '@/components/button-variants'
import { ScreenTitle } from '@/components/ScreenTitle'
import { SegmentedControl } from '@/components/SegmentedControl'
import { useIsPhone } from '@/hooks/use-is-phone'
import { useLanguage } from '@/hooks/use-language'
import { cn } from '@/lib/utils'

import { longDate } from './dates'
import { toolName } from './result-text'

export type ResultView = 'summary' | 'reviewer'

/** Summary or Reviewer: shareable view state, kept in the address by the route. */
export function ViewSwitch({
  view,
  onViewChange,
}: {
  view: ResultView
  onViewChange: (view: ResultView) => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <SegmentedControl<ResultView>
      label={t('result.view.label')}
      value={view}
      onChange={onViewChange}
      options={[
        { value: 'summary', label: t('result.view.summary') },
        { value: 'reviewer', label: t('result.view.reviewer') },
      ]}
    />
  )
}

/** "Checked on 6 October 2026 against the consolidated AI Act of 27 July 2026." */
function CheckedOnLine({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const date = longDate(result.as_of, language)
  let line = t('result.checkedOnOriginal', { date })
  if (result.law_version === 'amended') {
    line = result.law_text
      ? t('result.checkedOn', { date, lawDate: longDate(result.law_text.version_date, language) })
      : t('result.checkedOnAmended', { date })
  }
  return <p className="m-0 text-body-small text-slate">{line}</p>
}

/** "‹ Inventory", over the title on a phone (artboard `ResultMobile`), where the sidebar is folded. */
function BackToInventory(): JSX.Element {
  const { t } = useTranslation()
  return (
    <Link
      to="/app/inventory"
      className="inline-flex min-h-11 items-center gap-1 self-start text-label text-lens-blue no-underline hover:underline"
    >
      <span aria-hidden="true">‹</span>
      {t('nav.inventory')}
    </Link>
  )
}

/** The result's title row: the tool's name (or "Your tool" when it has none) and when it was
 *  checked, then the view switch and the actions. Buttons never shrink; the title wraps instead
 *  (localisation.md). On a phone the back link sits over the title and the compact law switch
 *  under it (artboard `ResultMobile`). */
export function ResultHeader({
  name,
  result,
  actions,
}: {
  name: string | null
  result: ClassificationResult
  actions: ReactNode
}): JSX.Element {
  const { t } = useTranslation()
  const isPhone = useIsPhone()
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="flex min-w-0 flex-col gap-1.5">
        {isPhone && <BackToInventory />}
        <ScreenTitle className="break-words">{toolName(t, name)}</ScreenTitle>
        <CheckedOnLine result={result} />
        {isPhone && <ScreenLawSwitch />}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2.5">{actions}</div>
    </div>
  )
}

/** "Draft documents": the documents a result leads to (P8a, P9), opened for its tool. */
export function DraftDocumentsLink({
  toolId,
  className,
}: {
  toolId: string
  className?: string
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <Link to="/app/documents" search={{ tool: toolId }} className={cn(buttonVariants(), className)}>
      {t('result.draftDocuments')}
    </Link>
  )
}
