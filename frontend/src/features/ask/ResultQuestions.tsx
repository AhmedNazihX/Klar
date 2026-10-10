import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { useQaThread } from '@/hooks/use-qa-thread'

import { resultThread } from './qa-history'
import { QaConversation } from './QaConversation'

const SUGGESTIONS = ['oversight', 'vendors'] as const

/** The questions-about-this-result thread of one run, keyed by it, so the next run starts afresh. */
export function ResultQuestions({
  toolId,
  runNo,
  result,
}: {
  toolId: string
  runNo: number
  result: ClassificationResult
}): JSX.Element {
  const thread = resultThread(toolId, runNo)
  return <ResultThread key={thread} thread={thread} result={result} />
}

/**
 * "Questions about this result" (artboards `Reviewer`, `Result`, `ResultMobile`): questions sent
 * with the result, so each answer cites the result's own provisions, under the result's law
 * version. Suggestions fill the field; nothing is sent until the user asks.
 */
function ResultThread({
  thread,
  result,
}: {
  thread: string
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const qa = useQaThread(thread, { lawVersion: result.law_version, result })
  const [draft, setDraft] = useState('')
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3.5 p-[22px]"
    >
      <h2 id={headingId} className="m-0 text-[17px] font-semibold text-ink">
        {t('ask.result.heading')}
      </h2>
      <QaConversation
        qa={qa}
        draft={draft}
        onDraftChange={setDraft}
        label={t('ask.result.label')}
        placeholder={t('ask.result.placeholder')}
        aboveField={
          <ul
            aria-label={t('ask.result.suggestionsLabel')}
            className="m-0 flex list-none flex-wrap gap-1.5 p-0"
          >
            {SUGGESTIONS.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => {
                    setDraft(t(`ask.result.${key}`))
                  }}
                  className="h-8 cursor-pointer rounded-pill border-0 px-3 text-[13px] text-ink glass-thin"
                >
                  {t(`ask.result.${key}`)}
                </button>
              </li>
            ))}
          </ul>
        }
        footer={<p className="m-0 text-micro text-slate">{t('ask.result.footer')}</p>}
      />
    </GlassPanel>
  )
}
