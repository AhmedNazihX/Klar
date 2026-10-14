import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, DocumentInfo } from '@/api'
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

/** Whether `document` is read under `lawVersion`: the amended text with the Omnibus, or the
 *  original one without it; the guidance under both. */
function isReadUnder(document: DocumentInfo, lawVersion: LawVersion): boolean {
  return lawVersion === 'amended'
    ? document.law_version !== 'original'
    : document.law_version !== 'amended' && !document.is_amending
}

/** The order of the artboard `Reviewer`'s "Texts used": the law first, then the guidance. */
const DOC_TYPE_ORDER: readonly DocumentInfo['doc_type'][] = ['law', 'guideline', 'code']

/** The texts `result` quotes: every text a citation comes from, whatever its law version (an
 *  amended result quotes recitals from the original Regulation, as the consolidated text has
 *  none), and the amending act when a quote is marked as changed by it and the act is read under
 *  `lawVersion` (the consolidated text carries its wording). The law first, then the guidance,
 *  each in the list's own order. */
function usedDocuments(
  documents: readonly DocumentInfo[],
  result: ClassificationResult,
  lawVersion: LawVersion,
): DocumentInfo[] {
  const citations = result.steps.flatMap((step) => step.citations ?? [])
  const cited = new Set(citations.map((citation) => citation.document_id))
  const isAmendmentQuoted = citations.some((citation) => citation.changed_by_omnibus)
  const used = documents.filter(
    (document) =>
      cited.has(document.doc_key) ||
      (document.is_amending && isAmendmentQuoted && isReadUnder(document, lawVersion)),
  )
  return DOC_TYPE_ORDER.flatMap((docType) => used.filter((d) => d.doc_type === docType))
}

/**
 * The legal texts Klar reads (`GET /documents`), each with its kind, a draft marked as one and a
 * text only in English marked as such, under `heading`, for the law version the answers or the
 * result use: on the Ask screen every text read under it, "Answers draw on" (artboard `Ask`); in
 * the reviewer view, "Texts used" (artboard `Reviewer`), only those the result quotes.
 */
export function SourceDocuments({
  heading,
  lawVersion,
  usedBy,
}: {
  heading: string
  lawVersion: LawVersion
  /** The result whose quoted texts alone are listed; every text without it. */
  usedBy?: ClassificationResult
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
          {(usedBy
            ? usedDocuments(documents.data, usedBy, lawVersion)
            : documents.data.filter((document) => isReadUnder(document, lawVersion))
          ).map((document) => {
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
