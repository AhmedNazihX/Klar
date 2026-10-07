import type { TFunction } from 'i18next'
import { useId, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, Obligation } from '@/api'
import { Citation } from '@/components/Citation'
import { GlassPanel } from '@/components/GlassPanel'
import { ObligationItem } from '@/components/ObligationItem'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import { longDate } from './dates'
import { provisionName } from './provision-names'
import { citationSource, dutyLabel, isTransparencyDuty } from './result-text'

/** The article column is wider in German (localisation.md: "Art. 26 Abs. 11"). */
const REFERENCE_WIDTH: Record<Language, number> = { en: 86, de: 112 }

/** The line under a duty: its Art. 111(2) marking (decision 026 item 24), or its condition. */
function dutyNote(t: TFunction, obligation: Obligation, language: Language): ReactNode {
  if (obligation.legacy === 'legacy_unchanged') return t('result.legacy.afterChange')
  if (obligation.legacy === 'legacy_public_authority') {
    return t('result.legacy.from', { date: longDate(obligation.applies_from, language) })
  }
  if (obligation.applies_if) return t('result.todo.onlyIf', { condition: obligation.applies_if })
  if (obligation.is_informational) return t('result.todo.forInformation')
  return null
}

/** The limited-risk intro promises a draft only when an Art. 50 duty has a template (C9 has
 *  them for 50(3) and 50(4)); otherwise it says what the duties ask, and no link shows. */
function limitedIntro(t: TFunction, result: ClassificationResult): string {
  const hasDraft = (result.obligations ?? []).some(
    (obligation) => isTransparencyDuty(obligation) && obligation.document,
  )
  return hasDraft ? t('result.todo.limited') : t('result.todo.limitedNoDraft')
}

function introFor(t: TFunction, result: ClassificationResult): string {
  if (result.risk_class === 'minimal_risk') return t('result.todo.minimal')
  if (result.risk_class === 'limited_risk') return limitedIntro(t, result)
  if ((result.obligations ?? []).length === 0) return t('result.todo.none')
  return result.role ? t(`result.todo.intro.${result.role}`) : t('result.todo.none')
}

/** "What you need to do": each duty as an action (C9's short label) with its article, its
 *  Art. 111(2) marking and a link to its draft document where C9 names one (for the Art. 50
 *  duties, the drafted disclosure: decision 026 item 19). */
export function DutiesPanel({ result }: { result: ClassificationResult }): JSX.Element {
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
      </div>
      {obligations.length > 0 && (
        <ul className="m-0 flex list-none flex-col p-0">
          {obligations.map((obligation) => (
            <ObligationItem
              key={`${obligation.article}:${obligation.duty}`}
              label={dutyLabel(obligation, language)}
              reference={provisionName(obligation.article, language)}
              referenceWidth={REFERENCE_WIDTH[language]}
              note={dutyNote(t, obligation, language)}
              tag={obligation.legacy ? t('result.legacy.tag') : undefined}
              isInformational={obligation.is_informational ?? false}
              docLabel={
                isTransparencyDuty(obligation)
                  ? t('result.todo.draftDisclosure')
                  : t('result.todo.draftDocument')
              }
              documentId={obligation.document}
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
