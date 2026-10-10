import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Citation as CitationData, QaAnswer } from '@/api'
import { Button } from '@/components/Button'
import { ChatMessage, type ChatCitation } from '@/components/ChatMessage'
import { Citation } from '@/components/Citation'
import { Composer } from '@/components/Composer'
import { ProvisionQuote } from '@/features/classify/ProvisionQuote'
import { isLawProvision, provisionName } from '@/features/classify/provision-names'
import { useLanguage } from '@/hooks/use-language'
import type { QaThread } from '@/hooks/use-qa-thread'

import type { QaEntry } from './qa-history'

/** The longest question the API takes (`aiact.api.qa.MAX_QUESTION_CHARS`). */
export const MAX_QUESTION_CHARS = 1000

/** The quote a chip opens: an article or Annex point from the corpus, in the screen's language
 *  at the answer's law version (never the copy an answer about a stored result carries, decision
 *  031); guidance as the answer cites it, labelled when it is a draft. */
function CitedQuote({
  citation,
  answer,
}: {
  citation: CitationData
  answer: QaAnswer
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  if (isLawProvision(citation.provision_id)) {
    return (
      <ProvisionQuote
        provisionId={citation.provision_id}
        result={{ law_version: answer.law_version, as_of: answer.as_of ?? '' }}
      />
    )
  }
  const source = t(
    citation.document_status === 'draft' ? 'result.citationSourceDraft' : 'result.citationSource',
    {
      provision: provisionName(citation.provision_id, language),
      language: t(`result.quoteLanguage.${citation.language}`),
    },
  )
  return (
    <Citation language={citation.language} source={source}>
      {citation.quote}
    </Citation>
  )
}

/** Why an answer cites nothing: outside the AI Act, or a compliance question. A refused question
 *  says why in its own text (decision 033), so it has no note. */
function noCitationNote(answer: QaAnswer, note: string): string | undefined {
  return answer.kind === 'answered' || answer.kind === 'refused' ? undefined : note
}

function KlarAnswer({ answer }: { answer: QaAnswer }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const isAnswered = answer.kind === 'answered'
  const citations: ChatCitation[] = isAnswered
    ? answer.citations.map((citation) => ({
        id: `${citation.document_id}:${citation.provision_id}`,
        label: provisionName(citation.provision_id, language),
        quote: <CitedQuote citation={citation} answer={answer} />,
      }))
    : []
  return (
    <ChatMessage
      from="klar"
      authorLabel={t('ask.klar')}
      citations={citations}
      citationsLabel={t('ask.citationsLabel')}
      note={noCitationNote(answer, t('ask.noCitations'))}
    >
      <p className="m-0 leading-[1.6] whitespace-pre-line">{answer.answer.trim()}</p>
    </ChatMessage>
  )
}

function Turn({ entry, onRetry }: { entry: QaEntry; onRetry: (id: string) => void }): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <ChatMessage from="user" authorLabel={t('ask.you')}>
        {entry.question}
      </ChatMessage>
      {entry.state === 'pending' && (
        <p role="status" className="m-0 self-start px-1 text-caption text-slate">
          {t('ask.answering')}
        </p>
      )}
      {entry.state === 'failed' && (
        <div className="flex flex-wrap items-center gap-3 self-start px-1">
          <p role="alert" className="m-0 text-caption text-ink-2">
            {entry.failure === 'busy' ? t('ask.busy') : t('ask.failed')}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onRetry(entry.id)
            }}
          >
            {t('ask.retry')}
          </Button>
        </div>
      )}
      {entry.state === 'answered' && entry.answer && <KlarAnswer answer={entry.answer} />}
    </>
  )
}

/**
 * A conversation with Klar: each question with Klar's answer and the provisions it rests on (or,
 * outside the AI Act, why none is cited), then the Composer. The field's text is the caller's,
 * so suggestions can fill it.
 */
export function QaConversation({
  qa,
  draft,
  onDraftChange,
  fieldId,
  label,
  placeholder,
  emptyText,
  aboveField,
  footer,
}: {
  qa: QaThread
  draft: string
  onDraftChange: (value: string) => void
  /** The field's id, so a suggestion that fills it can move the focus to it. */
  fieldId: string
  /** The field's accessible name. */
  label: string
  placeholder: string
  /** Shown before the first question; nothing when absent. */
  emptyText?: string
  /** Suggestions between the thread and the field. */
  aboveField?: ReactNode
  /** The lines under the field: the law version, the compliance note, the key hint. */
  footer: ReactNode
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <div aria-live="polite" className="flex flex-col gap-3.5">
        {qa.entries.length === 0 && emptyText && (
          <p className="m-0 text-body-small text-slate">{emptyText}</p>
        )}
        {qa.entries.map((entry) => (
          <Turn key={entry.id} entry={entry} onRetry={qa.retry} />
        ))}
      </div>
      <div className="flex flex-col gap-2.5">
        {aboveField}
        <Composer
          id={fieldId}
          value={draft}
          onChange={onDraftChange}
          onSend={qa.ask}
          label={label}
          placeholder={placeholder}
          sendLabel={t('ask.send')}
          isBusy={qa.isAsking}
          maxLength={MAX_QUESTION_CHARS}
        />
        {footer}
      </div>
    </>
  )
}
