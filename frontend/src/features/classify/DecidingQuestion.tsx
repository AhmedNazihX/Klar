import { useId, type JSX } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import type { AnswerOutcome, FollowUpQuestion } from '@/api'
import { Citation } from '@/components/Citation'
import { GlassPanel } from '@/components/GlassPanel'
import { LawDate } from '@/components/LawDate'
import { RiskPill } from '@/components/RiskPill'
import { useLanguage } from '@/hooks/use-language'

import { longDate, ROUTE_DATES } from './dates'
import { provisionName } from './provision-names'
import { citationSource } from './result-text'

/** "If yes": the class, the Annex point and the date duties would apply from. The engine gives
 *  the amended date; the original text's route date shows under the law switch (item 11). */
function IfYes({ outcome }: { outcome: AnswerOutcome }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const point = outcome.provision_id ? provisionName(outcome.provision_id, language) : ''
  const route = outcome.high_risk_route
  const amended = outcome.duties_from
  return (
    <>
      <RiskPill kind={outcome.risk_class} />
      <span>
        {amended ? (
          <Trans
            i18nKey="result.question.ifYesPoint"
            values={{ point }}
            components={{
              date: (
                <LawDate
                  amended={longDate(amended, language)}
                  original={longDate(route ? ROUTE_DATES[route].original : amended, language)}
                />
              ),
            }}
          />
        ) : (
          t('result.question.ifYesPointNoDate', { point })
        )}
      </span>
    </>
  )
}

/**
 * The question that decides a result Klar had to assume (artboard `ResultNeedsInfo`, decision 026
 * items 13 and 18): the question in the user's terms and why it matters, what a yes and a no
 * would mean, and the provisions it rests on. The model's words are shown as plain text.
 * Answering it is the follow-up loop's (P5b).
 */
export function DecidingQuestion({ question }: { question: FollowUpQuestion }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-4">
      <span className="text-caption font-normal text-slate">{t('result.question.eyebrow')}</span>
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {question.text}
      </h2>
      {question.hint && <p className="m-0 text-body-small text-slate">{question.hint}</p>}
      {question.if_yes && (
        <dl className="m-0 grid gap-2.5 md:grid-cols-2">
          <div className="flex flex-col gap-2 rounded-card-small px-4 py-3 glass-thin">
            <dt className="text-caption font-normal text-slate">{t('result.question.ifYes')}</dt>
            <dd className="m-0 flex flex-col items-start gap-2 text-body-small text-ink">
              <IfYes outcome={question.if_yes} />
            </dd>
          </div>
          <div className="flex flex-col gap-2 rounded-card-small px-4 py-3 glass-thin">
            <dt className="text-caption font-normal text-slate">{t('result.question.ifNo')}</dt>
            <dd className="m-0 text-body-small text-ink">{t('result.question.ifNoText')}</dd>
          </div>
        </dl>
      )}
      {(question.citations ?? []).map((citation) => (
        <Citation
          key={`${citation.document_id}:${citation.provision_id}`}
          language={citation.language}
          source={citationSource(t, citation, language)}
        >
          {citation.quote}
        </Citation>
      ))}
      <p className="m-0 text-caption font-normal text-ink-2">{t('result.question.assumption')}</p>
    </GlassPanel>
  )
}
