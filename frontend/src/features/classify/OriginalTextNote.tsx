import type { TFunction } from 'i18next'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import { useOriginalResult } from '@/hooks/use-original-run'
import type { Language } from '@/i18n'

import type { ClassificationRun } from './classification-store'
import { classLabel } from './law-comparison'
import { provisionName } from './provision-names'

/** What the original text's run found, against the result on the page (the amended text's). */
function originalLine(
  t: TFunction,
  amended: ClassificationResult,
  original: ClassificationResult | undefined,
  language: Language,
): string {
  if (!original) return t('result.original.notChecked')
  const riskClass = classLabel(t, original)
  if (riskClass !== classLabel(t, amended)) return t('result.original.differs', { riskClass })
  if (original.annex_point && original.annex_point !== amended.annex_point) {
    const basis = provisionName(original.annex_point, language)
    return t('result.original.otherBasis', { riskClass, basis })
  }
  return t('result.original.same', { riskClass })
}

/**
 * Under the original 2024 text, the summary says whose class it shows: the page keeps the tool's
 * result (the amended text's; only the route dates swap, decision 026 item 11), and the class
 * under the original text comes from the engine's own run (decision 020), compared in the
 * reviewer view. Nothing shows under the amended text, or on a result run under the original.
 */
export function OriginalTextNote({
  run,
  onCompare,
}: {
  run: ClassificationRun
  onCompare: () => void
}): JSX.Element | null {
  const { t } = useTranslation()
  const language = useLanguage()
  const law = useLawVersion()
  const original = useOriginalResult(run)
  if (law !== 'original' || run.result.law_version !== 'amended') return null
  return (
    <div
      role="note"
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-card-small px-4 py-3 glass-thin"
    >
      <p className="m-0 max-w-[720px] text-body-small text-ink-2">
        {originalLine(t, run.result, original, language)}
      </p>
      <Button variant="ghost" size="sm" onClick={onCompare}>
        {t('result.original.compare')}
      </Button>
    </div>
  )
}
