import { useId, useState, type JSX } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import type { AnswerOutcome, FollowUpQuestion } from '@/api'
import { Button } from '@/components/Button'
import { Citation } from '@/components/Citation'
import { GlassPanel } from '@/components/GlassPanel'
import { LawDate } from '@/components/LawDate'
import { RiskPill } from '@/components/RiskPill'
import { useLanguage } from '@/hooks/use-language'

import { longDate, routeDates } from './dates'
import { QuestionAnswer, RunAgainButton, type AnswerProps } from './FollowUpQuestions'
import { provisionName } from './provision-names'
import { citationSource } from './result-text'

/** "If yes": the class, the Annex point and the date duties would apply from. The engine gives
 *  the amended date; the original text's route date shows under the law switch (item 11). */
function IfYes({ outcome }: { outcome: AnswerOutcome }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const point = outcome.provision_id ? provisionName(outcome.provision_id, language) : ''
  const amended = outcome.duties_from
  const dates = amended ? routeDates(outcome.high_risk_route ?? null, amended) : null
  return (
    <>
      <RiskPill kind={outcome.risk_class} />
      <span>
        {dates ? (
          <Trans
            i18nKey="result.question.ifYesPoint"
            values={{ point }}
            components={{
              date: (
                <LawDate
                  amended={longDate(dates.amended, language)}
                  original={longDate(dates.original, language)}
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

type CopyState = 'idle' | 'copied' | 'failed'

/** "Not sure? Ask your vendor:" with the question to send them, and Copy question (decision 026
 *  item 3, as drawn). */
function VendorQuestion({ text }: { text: string }): JSX.Element {
  const { t } = useTranslation()
  const [copy, setCopy] = useState<CopyState>('idle')

  async function copyQuestion(): Promise<void> {
    try {
      await navigator.clipboard.writeText(text)
      setCopy('copied')
    } catch {
      // No clipboard (an insecure page, a refused permission): the question stays on screen.
      setCopy('failed')
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-card-small px-4 py-3 glass-thin">
      <span className="text-caption font-normal text-slate">{t('followUp.vendor.lead')}</span>
      <p className="m-0 text-body-small text-ink">
        {t('followUp.vendor.quoted', { question: text })}
      </p>
      <div className="flex flex-wrap items-center gap-2.5">
        <Button variant="ghost" size="sm" onClick={() => void copyQuestion()}>
          {t('followUp.vendor.copy')}
        </Button>
        <span role="status" className="text-caption font-normal text-slate">
          {copy === 'copied' && t('followUp.vendor.copied')}
          {copy === 'failed' && t('followUp.vendor.copyFailed')}
        </span>
      </div>
    </div>
  )
}

/**
 * The question that decides a result Klar had to assume (artboard `ResultNeedsInfo`, decision 026
 * items 13 and 18): the question in the user's terms and why it matters, its answers, what a yes
 * and a no would mean, the question to ask a vendor, and the provisions it rests on. The model's
 * words are shown as plain text. Answering it runs the checks again (the follow-up loop, P5b).
 */
export function DecidingQuestion({
  question,
  ...answers
}: { question: FollowUpQuestion } & AnswerProps): JSX.Element {
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
      <QuestionAnswer question={question} labelledBy={headingId} {...answers} />
      {answers.drafts[question.id]?.isFromProfile && (
        <p className="m-0 text-caption font-normal text-ink-2">{t('followUp.fromProfile')}</p>
      )}
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
      <VendorQuestion text={question.text} />
      {(question.citations ?? []).map((citation) => (
        <Citation
          key={`${citation.document_id}:${citation.provision_id}`}
          language={citation.language}
          source={citationSource(t, citation, language)}
        >
          {citation.quote}
        </Citation>
      ))}
      <RunAgainButton count={1} {...answers} />
      <p className="m-0 text-caption font-normal text-ink-2">{t('result.question.assumption')}</p>
    </GlassPanel>
  )
}
