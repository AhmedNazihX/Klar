import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { CheckedDraft, InterviewQuestion } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { WriteFailureMessage } from '@/features/welcome/WriteFailureMessage'
import { useSaveInterviewAnswer } from '@/hooks/use-interview-answers'

import { AnswerForm, type AnswerKind } from './AnswerForm'
import { interviewState, isSkeleton } from './interview'

export type InterviewPanelProps = {
  toolId: string
  template: string
  /** The document's questions, as its listing gives them. */
  questions: readonly InterviewQuestion[]
  /** Its draft; undefined while none can be shown (one that failed, say because its answers are
   *  too long to send): the interview then asks every question, so an answer can be shortened. */
  draft: CheckedDraft | undefined
  /** The answers stored for this document's template, by question key. */
  answers: Readonly<Record<string, string>>
}

function AnsweredItem({
  question,
  onChange,
}: {
  question: InterviewQuestion
  onChange: () => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <li className="flex items-center gap-2.5 text-label">
      <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-risk-minimal-tint text-risk-minimal">
        <Icon name="check" size={11} />
      </span>
      <span className="grow text-slate">{question.text}</span>
      <button
        type="button"
        onClick={onChange}
        aria-label={`${t('documents.interview.change')}: ${question.text}`}
        className="shrink-0 cursor-pointer border-0 bg-transparent p-0 text-caption text-lens-blue hover:underline"
      >
        {t('documents.interview.change')}
      </button>
    </li>
  )
}

/**
 * The guided interview (artboards `Documents`, `DocSkeleton`): "N of M answered", the answered
 * questions, the one asked now, and the ones still to come. A skeleton's interview covers the
 * section of the question asked. Each answer is saved to the user's own data (Supabase) and the
 * draft is redrawn from it; nothing is written in that the user didn't give.
 * Mount it per document (`key`), so skipped questions belong to that document.
 */
export function InterviewPanel({
  toolId,
  template,
  questions,
  draft,
  answers,
}: InterviewPanelProps): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set())
  const [chosenKey, setChosenKey] = useState<string | null>(null)
  const save = useSaveInterviewAnswer()
  const kind = answerKind(draft)
  const state = interviewState(questions, kind === 'skeleton', answers, skipped, chosenKey)
  const sectionHeading = draft?.document.sections.find((s) => s.key === state.section)?.heading
  const total = state.questions.length
  const answered = state.answered.length
  const { current } = state

  function saveAnswer(question: InterviewQuestion, answer: string): void {
    save.mutate(
      { toolId, template, questionKey: question.key, answer },
      {
        onSuccess: () => {
          setChosenKey(null)
        },
      },
    )
  }

  function skip(question: InterviewQuestion): void {
    setSkipped((previous) => new Set([...previous, question.key]))
    setChosenKey(null)
  }

  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-4 p-5.5">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id={headingId} className="m-0 text-[17px] font-semibold text-ink">
            {sectionHeading
              ? t('documents.interview.sectionTitle', { section: sectionHeading })
              : t('documents.interview.title')}
          </h2>
          <span className="shrink-0 text-caption text-slate">
            {t('documents.interview.progress', { answered, total })}
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={answered}
          aria-label={t('documents.interview.progress', { answered, total })}
          className="h-1.5 overflow-hidden rounded-pill bg-ink/10"
        >
          <div
            className="h-full rounded-pill bg-lens-blue"
            style={{ width: `${String(total ? (answered / total) * 100 : 100)}%` }}
          />
        </div>
      </div>
      {state.answered.length > 0 && (
        <ul
          aria-label={t('documents.interview.answeredList')}
          className="m-0 flex list-none flex-col gap-2 p-0"
        >
          {state.answered.map((question) => (
            <AnsweredItem
              key={question.key}
              question={question}
              onChange={() => {
                setChosenKey(question.key)
              }}
            />
          ))}
        </ul>
      )}
      {current ? (
        <AnswerForm
          key={current.key}
          question={current}
          given={answers[current.key] ?? ''}
          kind={kind}
          isSaving={save.isPending}
          onSave={(answer) => {
            saveAnswer(current, answer)
          }}
          onSkip={() => {
            skip(current)
          }}
        />
      ) : (
        <InterviewEnd
          hasSkipped={state.upcoming.length > 0}
          onShowSkipped={() => {
            setSkipped(new Set())
          }}
        />
      )}
      {save.isError && <WriteFailureMessage error={save.error} kind="save" />}
      {state.upcoming.length > 0 && (
        <ul
          aria-label={t('documents.interview.upcomingList')}
          className="m-0 flex list-none flex-col gap-2 p-0"
        >
          {state.upcoming.map((question) => (
            <li key={question.key} className="flex items-center gap-2.5 text-label text-ink/70">
              <span className="size-5 shrink-0 rounded-full shadow-[inset_0_0_0_1.5px_rgb(15_27_45/0.35)]" />
              {question.text}
            </li>
          ))}
        </ul>
      )}
    </GlassPanel>
  )
}

function answerKind(draft: CheckedDraft | undefined): AnswerKind {
  if (!draft) return 'unknown'
  return isSkeleton(draft) ? 'skeleton' : 'notice'
}

function InterviewEnd({
  hasSkipped,
  onShowSkipped,
}: {
  hasSkipped: boolean
  onShowSkipped: () => void
}): JSX.Element {
  const { t } = useTranslation()
  if (!hasSkipped) {
    return <p className="m-0 text-body-small text-ink-2">{t('documents.interview.done')}</p>
  }
  return (
    <div className="flex flex-col items-start gap-1.5">
      <p className="m-0 text-body-small text-ink-2">{t('documents.interview.skippedAll')}</p>
      <button
        type="button"
        onClick={onShowSkipped}
        className="cursor-pointer border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
      >
        {t('documents.interview.showSkipped')}
      </button>
    </div>
  )
}
