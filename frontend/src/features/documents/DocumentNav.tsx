import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ListedDocument } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { provisionName } from '@/features/classify/provision-names'
import { useLanguage } from '@/hooks/use-language'
import { cn } from '@/lib/utils'

import type { SelectedDocument } from './document-selection'
import type { AnswersByTemplate } from './interview-answers'
import { documentTitle, unansweredCount } from './interview'

/** One tool's group in the list: its documents once listed, or why there are none to show. */
export type NavGroup = {
  toolId: string
  toolName: string
  documents: readonly ListedDocument[] | undefined
  /** The answers stored for the tool, which say what each document still needs. */
  answers: AnswersByTemplate
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

/** "Art. 26(7). Needs 2 answers" or "Art. 26(7). Ready to review" (artboard `Documents`),
 *  counted from the document's questions and the answers stored for it, as the drafter counts. */
function DocumentStatus({
  document,
  answers,
}: {
  document: ListedDocument
  answers: AnswersByTemplate
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const article = provisionName(document.article, language)
  const unanswered = unansweredCount(document.questions, answers[document.template] ?? {})
  return (
    <span className="text-caption text-slate">
      {unanswered > 0
        ? t('documents.needsAnswers', { article, count: unanswered })
        : t('documents.readyToReview', { article })}
    </span>
  )
}

function GroupBody({
  group,
  selected,
}: {
  group: NavGroup
  selected: SelectedDocument | null
}): JSX.Element {
  const { t } = useTranslation()
  if (group.isError) {
    return (
      <div role="alert" className="flex flex-col items-start gap-1 px-3 py-2 text-caption">
        <span className="text-ink">{t('documents.draftFailed')}</span>
        <button
          type="button"
          onClick={group.onRetry}
          className="cursor-pointer border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
        >
          {t('documents.tryAgain')}
        </button>
      </div>
    )
  }
  if (group.isLoading || !group.documents) {
    return <p className="m-0 px-3 py-2 text-caption text-slate">{t('documents.drafting')}</p>
  }
  if (group.documents.length === 0) {
    return <p className="m-0 px-3 py-2 text-caption text-slate">{t('documents.noDocuments')}</p>
  }
  return (
    <ul className="m-0 flex list-none flex-col gap-1 p-0">
      {group.documents.map((document) => {
        const isCurrent =
          selected?.tool.toolId === group.toolId && selected.document.template === document.template
        return (
          <li key={document.template}>
            <Link
              to="/app/documents/$documentId"
              params={{ documentId: document.template }}
              search={(previous) => ({ ...previous, tool: group.toolId })}
              aria-current={isCurrent ? 'page' : undefined}
              className={cn(
                'flex flex-col gap-1 rounded-card-small p-3 text-ink no-underline',
                isCurrent
                  ? 'bg-white/80 shadow-[inset_0_1px_0_#fff,0_4px_14px_-6px_rgb(28_44_86/0.28)]'
                  : 'hover:bg-white/45',
              )}
            >
              <span className="text-body-small font-semibold">
                {documentTitle(document, group.answers[document.template] ?? {})}
              </span>
              <DocumentStatus document={document} answers={group.answers} />
            </Link>
          </li>
        )
      })}
    </ul>
  )
}

/** The documents of every tool, grouped by tool (decision 026 item 20), with their statuses. A
 *  document's title is the one its stored answers give it (`documentTitle`). */
export function DocumentNav({
  groups,
  selected,
  className,
}: {
  groups: readonly NavGroup[]
  selected: SelectedDocument | null
  className?: string
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel
      as="div"
      padded={false}
      className={cn('flex w-full shrink-0 flex-col gap-2.5 px-3.5 py-5', className)}
    >
      <nav aria-label={t('documents.navLabel')} className="flex flex-col gap-2.5">
        {groups.map((group, index) => (
          <section
            key={group.toolId}
            aria-label={t('documents.forTool', { tool: group.toolName })}
            className={cn('flex flex-col gap-1', index > 0 && 'border-t border-hairline pt-2.5')}
          >
            <h2 className="m-0 px-2 pb-1 text-caption font-medium text-slate">
              {t('documents.forTool', { tool: group.toolName })}
            </h2>
            <GroupBody group={group} selected={selected} />
          </section>
        ))}
      </nav>
    </GlassPanel>
  )
}
