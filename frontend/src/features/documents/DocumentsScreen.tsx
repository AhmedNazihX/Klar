import { useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { SizeClass } from '@/api'
import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'
import { useDocumentDrafts, type DraftInputs } from '@/hooks/use-document-drafts'
import { useInterviewAnswers } from '@/hooks/use-interview-answers'
import { useLanguage } from '@/hooks/use-language'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

import { ChecksPanel } from './ChecksPanel'
import { DocumentNav, type NavGroup } from './DocumentNav'
import { selectDocument, sessionTools, type SelectedDocument } from './document-selection'
import { DownloadButtons } from './DownloadButtons'
import { DraftView } from './DraftView'
import { InterviewPanel } from './InterviewPanel'
import { isSkeleton } from './interview'

export type DocumentsScreenProps = {
  /** The template id of the document to show (`/app/documents/<id>`); the first one without. */
  documentId?: string
  /** The tool it belongs to (`?tool=`); the first tool that has the document without. */
  toolId?: string
}

/** No tool classified this session: nothing to draft yet. */
function NoTools(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <ScreenTitle>{t('screen.documents')}</ScreenTitle>
      <GlassPanel className="flex flex-col items-start gap-4">
        <p className="m-0 text-body text-slate">{t('documents.empty.body')}</p>
        <Link to="/app/classify" className={buttonVariants()}>
          {t('documents.empty.action')}
        </Link>
      </GlassPanel>
    </>
  )
}

function Breadcrumb({ toolName }: { toolName: string }): JSX.Element {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('documents.breadcrumb')} className="flex gap-2 text-label">
      <Link to="/app/documents" className="text-slate no-underline hover:underline">
        {t('nav.documents')}
      </Link>
      <span aria-hidden="true" className="text-slate">
        /
      </span>
      <span className="font-medium text-ink">{toolName}</span>
    </nav>
  )
}

/** The document on show, its interview and its checks, with the downloads above. */
function SelectedDocumentView({
  selected,
  answers,
  sizeClass,
  toolName,
}: {
  selected: SelectedDocument
  answers: Readonly<Record<string, string>>
  sizeClass: SizeClass | null
  toolName: string
}): JSX.Element {
  const language = useLanguage()
  const { tool, draft } = selected
  const template = draft.document.template
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Breadcrumb toolName={toolName} />
        <DownloadButtons
          request={{ result: tool.result, template, language, size_class: sizeClass, answers }}
        />
      </div>
      <div className="flex min-w-0 flex-col items-stretch gap-5 2xl:flex-row 2xl:items-start">
        <DraftView document={draft.document} />
        <div className="flex w-full shrink-0 flex-col gap-4 2xl:w-[340px]">
          <InterviewPanel
            key={`${tool.toolId}:${template}`}
            toolId={tool.toolId}
            draft={draft}
            answers={answers}
          />
          <ChecksPanel checks={draft.checks} isSkeleton={isSkeleton(draft)} />
        </div>
      </div>
    </>
  )
}

/**
 * Draft documents (artboards `Documents`, `DocSkeleton`; decision 026 items 20 and 21): every
 * tool's documents grouped by tool with their statuses, the selected document on white, its
 * guided interview and its automatic checks, and the Word and PDF downloads. The drafts come
 * from the API, built from the tool's result and the answers the user saved; the company's size
 * class comes from its profile.
 */
export function DocumentsScreen({ documentId, toolId }: DocumentsScreenProps): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const queryClient = useQueryClient()
  // The session's tools are read once: the cache doesn't gain a tool while this screen is open.
  const [tools] = useState(() => sessionTools(queryClient))
  const overview = useUserDataOverview()
  const sizeClass = overview.data?.profile?.sizeClass ?? null
  const answerQueries = useInterviewAnswers(tools.map((tool) => tool.toolId))
  const inputs: DraftInputs[] = tools.map((tool, index) => ({
    tool,
    hasAnswers: answerQueries[index]?.data !== undefined,
    language,
    sizeClass,
  }))
  const draftQueries = useDocumentDrafts(inputs)
  if (tools.length === 0) return <NoTools />

  const groups: NavGroup[] = tools.map((tool, index) => {
    const drafts = draftQueries[index]
    const answers = answerQueries[index]
    return {
      toolId: tool.toolId,
      toolName: tool.name || t('classify.untitled'),
      drafts: drafts?.data,
      isLoading: Boolean(drafts?.isPending || answers?.isPending),
      isError: Boolean(drafts?.isError || answers?.isError),
      onRetry: () => {
        void (answers?.isError ? answers.refetch() : drafts?.refetch())
      },
    }
  })
  const selected = selectDocument(
    tools.map((tool, index) => ({ tool, drafts: draftQueries[index]?.data })),
    documentId,
    toolId,
  )
  const selectedIndex = selected ? tools.indexOf(selected.tool) : -1
  const selectedAnswers = answerQueries[selectedIndex]?.data ?? {}
  const isSettled = groups.every((group) => !group.isLoading)

  return (
    <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
      <DocumentNav groups={groups} selected={selected} />
      <div className="flex min-w-0 grow flex-col gap-5">
        {selected ? (
          <SelectedDocumentView
            selected={selected}
            answers={selectedAnswers[selected.draft.document.template] ?? {}}
            sizeClass={sizeClass}
            toolName={groups[selectedIndex]?.toolName ?? ''}
          />
        ) : (
          isSettled && (
            <GlassPanel>
              <h1 className="m-0 text-body font-semibold text-ink">{t('screen.document')}</h1>
              <p className="m-0 mt-2 text-body text-slate">{t('documents.notFound')}</p>
            </GlassPanel>
          )
        )}
      </div>
    </div>
  )
}
