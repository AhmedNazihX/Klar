import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import type { QaThread } from '@/hooks/use-qa-thread'

import { QaConversation } from './QaConversation'

const SUGGESTIONS = ['oversight', 'vendors'] as const

/**
 * "Questions about this result" (artboards `Reviewer`, `Result`, `ResultMobile`): questions sent
 * with the result, so each answer cites the result's own provisions, under the result's law
 * version. Suggestions fill the field and move the focus to it; nothing is sent until the user
 * asks.
 */
export function ResultQuestions({ qa }: { qa: QaThread }): JSX.Element {
  const { t } = useTranslation()
  const [draft, setDraft] = useState('')
  const headingId = useId()
  const fieldId = useId()
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
        fieldId={fieldId}
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
                    document.getElementById(fieldId)?.focus()
                  }}
                  className="h-11 cursor-pointer rounded-pill md:h-8 border-0 px-3 text-[13px] text-ink glass-thin"
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
