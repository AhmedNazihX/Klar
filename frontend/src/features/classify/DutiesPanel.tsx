import type { TFunction } from 'i18next'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Citation } from '@/components/Citation'
import { GlassPanel } from '@/components/GlassPanel'
import { ObligationItem } from '@/components/ObligationItem'
import { useLanguage } from '@/hooks/use-language'

import { OriginalDatesNote } from './OriginalDatesNote'
import { provisionName } from './provision-names'
import {
  citationSource,
  DUTY_REFERENCE_WIDTH,
  dutyLabel,
  dutyNote,
  isTransparencyDuty,
} from './result-text'

/** The limited-risk intro promises a draft only when an Art. 50 duty has a template (C9 has
 *  them for 50(3) and 50(4)); otherwise it says what the duties ask, and no link shows. */
function limitedIntro(t: TFunction, result: ClassificationResult): string {
  const hasDraft = (result.obligations ?? []).some(
    (obligation) => isTransparencyDuty(obligation) && obligation.document,
  )
  return hasDraft ? t('result.todo.limited') : t('result.todo.limitedNoDraft')
}

function introFor(t: TFunction, result: ClassificationResult): string {
  // The engine lists no duties under the original text (decision 020): it says so, not "none".
  if (result.law_version === 'original') return t('result.todo.notModelled')
  if (result.risk_class === 'minimal_risk') return t('result.todo.minimal')
  if (result.risk_class === 'limited_risk') return limitedIntro(t, result)
  if ((result.obligations ?? []).length === 0) return t('result.todo.none')
  return result.role ? t(`result.todo.intro.${result.role}`) : t('result.todo.none')
}

/** "What you need to do": each duty as an action (C9's short label) with its article, its
 *  Art. 111(2) marking and a link to its draft document where C9 names one (for the Art. 50
 *  duties, the drafted disclosure: decision 026 item 19). */
export function DutiesPanel({
  result,
  toolId,
}: {
  result: ClassificationResult
  /** The tool the result is for; its duties' documents open for it. */
  toolId?: string
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const obligations = result.obligations ?? []
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-1 flex-col gap-4 px-7 py-6.5"
    >
      <div className="flex flex-col gap-2">
        <h2 id={headingId} className="m-0 text-heading-panel text-ink">
          {t('result.todo.heading')}
        </h2>
        <p className="m-0 max-w-[620px] text-body-small text-slate">{introFor(t, result)}</p>
        <OriginalDatesNote result={result} />
      </div>
      {obligations.length > 0 && (
        <ul className="m-0 flex list-none flex-col p-0">
          {obligations.map((obligation) => (
            <ObligationItem
              key={`${obligation.article}:${obligation.duty}`}
              label={dutyLabel(obligation, language)}
              reference={provisionName(obligation.article, language)}
              referenceWidth={DUTY_REFERENCE_WIDTH[language]}
              note={dutyNote(t, obligation, language)}
              tag={obligation.legacy ? t('result.legacy.tag') : undefined}
              isInformational={obligation.is_informational ?? false}
              docLabel={
                isTransparencyDuty(obligation)
                  ? t('result.todo.draftDisclosure')
                  : t('result.todo.draftDocument')
              }
              documentId={obligation.document}
              toolId={toolId}
            />
          ))}
        </ul>
      )}
    </GlassPanel>
  )
}

/** An out-of-scope result has no duty list: it says why, with the provision quoted (item 19). */
export function OutOfScopePanel({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const scope = result.steps.find((step) => step.step === 'scope')
  const [quote] = scope?.citations ?? []
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-1 flex-col gap-4 px-7 py-6.5"
    >
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {t('result.outOfScope.heading')}
      </h2>
      {scope && <p className="m-0 text-body-small text-ink">{scope.decision}</p>}
      {quote && (
        <Citation language={quote.language} source={citationSource(t, quote, language)}>
          {quote.quote}
        </Citation>
      )}
      <p className="m-0 text-body-small text-slate">{t('result.outOfScope.intro')}</p>
    </GlassPanel>
  )
}
