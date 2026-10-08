import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { SizeClass } from '@/api'
import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'
import {
  documentFailure,
  useDocumentDraft,
  useDocumentLists,
  type DocumentTool,
} from '@/hooks/use-document-drafts'
import { useInterviewAnswers } from '@/hooks/use-interview-answers'
import { useInventoryTools } from '@/hooks/use-inventory-tools'
import { useLanguage } from '@/hooks/use-language'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

import { ChecksPanel } from './ChecksPanel'
import { DocumentNav, type NavGroup } from './DocumentNav'
import { documentTools, selectDocument, type SelectedDocument } from './document-selection'
import { DownloadButtons } from './DownloadButtons'
import { DraftView } from './DraftView'
import type { TemplateAnswers } from './interview'
import { isSkeleton } from './interview'
import { InterviewPanel } from './InterviewPanel'

export type DocumentsScreenProps = {
  /** The template id of the document to show (`/app/documents/<id>`); the first one without. */
  documentId?: string
  /** The tool it belongs to (`?tool=`); the first tool that has the document without. */
  toolId?: string
}

/** No tool with a result in the inventory: nothing to draft yet. */
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

/** The inventory is loading, or couldn't be read (with Try again). */
function ToolsState({ onRetry }: { onRetry?: () => void }): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <ScreenTitle>{t('screen.documents')}</ScreenTitle>
      <GlassPanel className="flex flex-col items-start gap-3">
        {onRetry ? (
          <div role="alert" className="flex flex-col items-start gap-2">
            <p className="m-0 text-body text-ink">{t('documents.toolsFailed')}</p>
            <button
              type="button"
              onClick={onRetry}
              className="cursor-pointer border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
            >
              {t('documents.tryAgain')}
            </button>
          </div>
        ) : (
          <p className="m-0 text-body text-slate">{t('documents.toolsLoading')}</p>
        )}
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

const DRAFT_FAILURE_KEYS = {
  'too-large': 'documents.tooLarge',
  'checks-failed': 'documents.documentFailed',
  busy: 'documents.documentFailed',
  failed: 'documents.documentFailed',
} as const

/** The document on show: drafted with its answers, its interview and its checks, with the
 *  downloads above. The downloads post what the draft was made from, size class included. */
function SelectedDocumentView({
  selected,
  answers,
  hasAnswers,
  sizeClass,
  toolName,
}: {
  selected: SelectedDocument
  answers: TemplateAnswers
  hasAnswers: boolean
  sizeClass: SizeClass | null
  toolName: string
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const { tool, document } = selected
  const { template } = document
  const draft = useDocumentDraft({ tool, template, hasAnswers, language, sizeClass })
  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <Breadcrumb toolName={toolName} />
      {draft.data && (
        <DownloadButtons
          request={{ result: tool.result, template, language, size_class: sizeClass, answers }}
        />
      )}
    </div>
  )
  if (!draft.data) {
    return (
      <>
        {header}
        <GlassPanel>
          {draft.isError ? (
            <div role="alert" className="flex flex-col items-start gap-2">
              <p className="m-0 text-body text-ink">
                {t(DRAFT_FAILURE_KEYS[documentFailure(draft.error)])}
              </p>
              <button
                type="button"
                onClick={() => void draft.refetch()}
                className="cursor-pointer border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
              >
                {t('documents.tryAgain')}
              </button>
            </div>
          ) : (
            <p className="m-0 text-body text-slate">{t('documents.draftingOne')}</p>
          )}
        </GlassPanel>
      </>
    )
  }
  return (
    <>
      {header}
      <div className="flex min-w-0 flex-col items-stretch gap-5 2xl:flex-row 2xl:items-start">
        <DraftView document={draft.data.document} />
        <div className="flex w-full shrink-0 flex-col gap-4 2xl:w-[340px]">
          <InterviewPanel
            key={`${tool.toolId}:${template}`}
            toolId={tool.toolId}
            draft={draft.data}
            answers={answers}
          />
          <ChecksPanel checks={draft.data.checks} isSkeleton={isSkeleton(draft.data)} />
        </div>
      </div>
    </>
  )
}

/**
 * Draft documents (artboards `Documents`, `DocSkeleton`; decision 026 items 20 and 21): the
 * documents of every tool in the inventory, grouped by tool with their statuses, the selected
 * document on white, its guided interview and its automatic checks, and the Word and PDF
 * downloads. A tool's id is the inventory's (`systems.id`, P6), which its answers are saved
 * under. The list comes from the API per tool; the document on show is drafted on its own, from
 * the tool's result and that document's saved answers; the size class is the profile's.
 */
export function DocumentsScreen({ documentId, toolId }: DocumentsScreenProps): JSX.Element {
  const inventory = useInventoryTools()
  if (inventory.isError) return <ToolsState onRetry={() => void inventory.refetch()} />
  if (inventory.isLoading) return <ToolsState />
  const tools = documentTools(inventory.data ?? [])
  if (tools.length === 0) return <NoTools />
  return <ToolDocuments tools={tools} documentId={documentId} toolId={toolId} />
}

function ToolDocuments({
  tools,
  documentId,
  toolId,
}: DocumentsScreenProps & { tools: readonly DocumentTool[] }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const overview = useUserDataOverview()
  const sizeClass = overview.data?.profile?.sizeClass ?? null
  const answerQueries = useInterviewAnswers(tools.map((tool) => tool.toolId))
  const listQueries = useDocumentLists(tools, language)

  const groups: NavGroup[] = tools.map((tool, index) => {
    const list = listQueries[index]
    const answers = answerQueries[index]
    return {
      toolId: tool.toolId,
      toolName: tool.name || t('classify.untitled'),
      documents: list?.data,
      answers: answers?.data ?? {},
      isLoading: Boolean(list?.isPending || answers?.isPending),
      isError: Boolean(list?.isError || answers?.isError),
      onRetry: () => {
        void (answers?.isError ? answers.refetch() : list?.refetch())
      },
    }
  })
  const selected = selectDocument(
    tools.map((tool, index) => ({ tool, documents: listQueries[index]?.data })),
    documentId,
    toolId,
  )
  const selectedIndex = selected ? tools.indexOf(selected.tool) : -1
  const selectedAnswers = answerQueries[selectedIndex]?.data
  const isSettled = groups.every((group) => !group.isLoading)

  return (
    <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
      <DocumentNav groups={groups} selected={selected} />
      <div className="flex min-w-0 grow flex-col gap-5">
        {selected ? (
          <SelectedDocumentView
            key={`${selected.tool.toolId}:${selected.document.template}`}
            selected={selected}
            answers={selectedAnswers?.[selected.document.template] ?? {}}
            hasAnswers={selectedAnswers !== undefined}
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
