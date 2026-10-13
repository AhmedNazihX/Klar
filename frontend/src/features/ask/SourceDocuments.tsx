import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DocumentInfo } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import type { LawVersion } from '@/components/LawSwitch'
import { useCorpusDocuments } from '@/hooks/use-corpus-documents'
import { useLanguage } from '@/hooks/use-language'
import { cn } from '@/lib/utils'

type DocumentKind = 'consolidated' | 'law' | 'final' | 'draft'

function documentKind(document: DocumentInfo): DocumentKind {
  if (document.status === 'consolidated') return 'consolidated'
  if (document.doc_type === 'law') return 'law'
  return document.status
}

/** The texts read under `lawVersion`: the amended text with the Omnibus, or the original one
 *  without it; the guidance under both. */
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

/**
 * The legal texts Klar reads (`GET /documents`), each with its kind, a draft marked as one and a
 * text only in English marked as such, under `heading`: "Answers draw on" on the Ask screen
 * (artboard `Ask`), "Texts used" in the reviewer view (artboard `Reviewer`). Every text the
 * corpus holds in the screen's language, under the law version the answers or the result use.
 */
export function SourceDocuments({
  heading,
  lawVersion,
}: {
  heading: string
  lawVersion: LawVersion
}): JSX.Element {
  const { t } = useTranslation()
  const documents = useCorpusDocuments(useLanguage())
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3 p-6">
      <h2 id={headingId} className="m-0 text-[17px] font-semibold text-ink">
        {heading}
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
