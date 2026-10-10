import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DocumentInfo } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import type { LawVersion } from '@/components/LawSwitch'
import { ScreenTitle } from '@/components/ScreenTitle'
import { useCorpusDocuments } from '@/hooks/use-corpus-documents'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import { useQaThread } from '@/hooks/use-qa-thread'
import { cn } from '@/lib/utils'

import { ASK_THREAD } from './qa-history'
import { QaConversation } from './QaConversation'

const TRY_ASKING = ['oversight', 'internal', 'omnibus'] as const

type DocumentKind = 'consolidated' | 'law' | 'final' | 'draft'

function documentKind(document: DocumentInfo): DocumentKind {
  if (document.status === 'consolidated') return 'consolidated'
  if (document.doc_type === 'law') return 'law'
  return document.status
}

/** The texts the answers use under `lawVersion`: the amended text with the Omnibus, or the
 *  original one without it; the guidance under both. */
function shownDocuments(
  documents: readonly DocumentInfo[],
  lawVersion: LawVersion,
): DocumentInfo[] {
  return documents.filter((document) =>
    lawVersion === 'amended'
      ? document.law_version !== 'original'
      : document.law_version !== 'amended' && !document.is_amending,
  )
}

/** "Answers draw on": every text the corpus holds in the screen's language, with its kind, a
 *  draft marked as one and a text only in English marked as such. */
function AnswersDrawOn({ lawVersion }: { lawVersion: LawVersion }): JSX.Element {
  const { t } = useTranslation()
  const documents = useCorpusDocuments(useLanguage())
  return (
    <GlassPanel as="section" aria-labelledby="ask-sources" className="flex flex-col gap-3 p-6">
      <h2 id="ask-sources" className="m-0 text-[17px] font-semibold text-ink">
        {t('ask.sources.heading')}
      </h2>
      {documents.isPending && (
        <p role="status" className="m-0 text-caption text-slate">
          {t('ask.sources.loading')}
        </p>
      )}
      {documents.isError && (
        <p className="m-0 text-caption text-slate">{t('ask.sources.failed')}</p>
      )}
      {documents.isSuccess && (
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0 text-body-small">
          {shownDocuments(documents.data, lawVersion).map((document) => {
            const kind = documentKind(document)
            return (
              <li key={document.doc_key} className="flex items-start justify-between gap-2.5">
                <span className="min-w-0 text-ink">
                  {document.title}
                  {document.english_only && (
                    <span className="block text-xs text-slate">{t('ask.sources.englishOnly')}</span>
                  )}
                </span>
                <span
                  className={cn(
                    'shrink-0 text-xs whitespace-nowrap',
                    kind === 'draft' ? 'font-semibold text-lens-blue' : 'text-slate',
                  )}
                >
                  {t(`ask.sources.kind.${kind}`)}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </GlassPanel>
  )
}

/**
 * Ask about the Act (artboard `Ask`): the conversation with Klar beside "Try asking" and the
 * texts the answers draw on. The thread stays for the browser session (decision 026 item 6).
 */
export function AskScreen(): JSX.Element {
  const { t } = useTranslation()
  const lawVersion = useLawVersion()
  const qa = useQaThread(ASK_THREAD, { lawVersion })
  const [draft, setDraft] = useState('')
  const fieldId = useId()
  // A fragment: the title, the panels and the notice stay the screen's direct children (load motion).
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <ScreenTitle>{t('screen.ask')}</ScreenTitle>
        <p className="m-0 text-body text-slate">{t('ask.subtitle')}</p>
      </div>
      <div className="flex min-w-0 flex-col items-stretch gap-5 lg:flex-row lg:items-start">
        <GlassPanel
          as="section"
          aria-label={t('ask.conversation')}
          className="flex min-w-0 flex-1 flex-col gap-[18px] p-5 md:p-[26px]"
        >
          <QaConversation
            qa={qa}
            draft={draft}
            onDraftChange={setDraft}
            fieldId={fieldId}
            label={t('ask.label')}
            placeholder={t('ask.placeholder')}
            emptyText={t('ask.empty')}
            footer={
              <div className="flex flex-col gap-1 border-t border-ink/8 pt-2 md:flex-row md:justify-between md:gap-4">
                <p className="m-0 text-micro text-slate">{t(`ask.footer.${lawVersion}`)}</p>
                <p className="m-0 hidden text-micro whitespace-nowrap text-slate md:block">
                  {t('ask.hint')}
                </p>
              </div>
            }
          />
        </GlassPanel>
        <div className="flex min-w-0 flex-col gap-5 lg:w-[340px] lg:shrink-0">
          <GlassPanel as="section" aria-labelledby="ask-try" className="flex flex-col gap-3 p-6">
            <h2 id="ask-try" className="m-0 text-[17px] font-semibold text-ink">
              {t('ask.tryAsking.heading')}
            </h2>
            <div className="flex flex-col gap-2">
              {TRY_ASKING.map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    // The field takes the focus, so Enter then asks the question.
                    setDraft(t(`ask.tryAsking.${key}`))
                    document.getElementById(fieldId)?.focus()
                  }}
                  className="lift cursor-pointer rounded-item border-0 px-3.5 py-2.5 text-left text-body-small leading-[1.4] text-ink glass-thin"
                >
                  {t(`ask.tryAsking.${key}`)}
                </button>
              ))}
            </div>
          </GlassPanel>
          <AnswersDrawOn lawVersion={lawVersion} />
        </div>
      </div>
    </>
  )
}
