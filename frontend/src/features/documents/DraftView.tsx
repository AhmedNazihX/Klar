import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DraftDocument, DraftSection } from '@/api'
import { Citation } from '@/components/Citation'
import { StatusPill } from '@/components/StatusPill'
import { longDate } from '@/features/classify/dates'
import { citationSource } from '@/features/classify/result-text'
import { useLanguage } from '@/hooks/use-language'

import { sectionAnchor } from './interview'
import { SectionStatusPill } from './SectionStatusPill'

function Section({
  section,
  isSkeleton,
  toFillIn,
}: {
  section: DraftSection
  isSkeleton: boolean
  toFillIn?: string
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const paragraphs = section.paragraphs ?? []
  const isWaiting = section.status !== 'drafted'
  // A tag says where content came from; the template's own wording carries none.
  const provenance =
    paragraphs.length > 0 && section.provenance !== 'template' ? section.provenance : null
  // An answer's paragraph is keyed by its question; a pre-filled one by its own text.
  const unanswered = section.unanswered ?? []
  const paragraphKeys = (section.question_keys ?? []).filter((key) => !unanswered.includes(key))
  return (
    <section
      id={sectionAnchor(section.key)}
      aria-label={section.heading}
      className="flex scroll-mt-6 flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="m-0 text-body-small font-semibold text-ink">{section.heading}</h2>
        {isSkeleton && <SectionStatusPill section={section} />}
      </div>
      {paragraphs.map((paragraph, index) => (
        <p
          key={paragraphKeys[index] ?? paragraph}
          className="m-0 font-serif text-[17px] leading-relaxed whitespace-pre-line text-ink-2"
        >
          {paragraph}
        </p>
      ))}
      {(section.quotes ?? []).map((quote) => (
        <Citation
          key={quote.provision_id}
          language={quote.language}
          source={citationSource(t, quote, language)}
        >
          {quote.quote}
        </Citation>
      ))}
      {provenance && (
        <span className="text-micro text-slate">{t(`documents.provenance.${provenance}`)}</span>
      )}
      {isWaiting && section.requirement && (
        <Citation
          language={section.requirement.language}
          source={citationSource(t, section.requirement, language)}
        >
          {section.requirement.quote}
        </Citation>
      )}
      {isWaiting && (
        <p className="m-0 rounded-field border-[1.5px] border-dashed border-lens-blue/40 bg-lens-blue-soft px-3.5 py-2.5 text-body-small font-medium text-lens-blue">
          {toFillIn ?? t('documents.toFillIn')}
        </p>
      )}
    </section>
  )
}

/** The document on white (artboards `Documents`, `DocSkeleton`): its title with the DRAFT stamp,
 *  the law version and date, the note, every section, and the notice. A skeleton's page has its
 *  own heading (`SkeletonHeader`), so a skeleton's title here is a level below it. A long title
 *  breaks inside its words rather than pushing a phone's page sideways (German
 *  "Qualitätsmanagementsystem"). User text is shown as text, never as markup. */
export function DraftView({
  document,
  isSkeleton,
  toFillIn,
}: {
  document: DraftDocument
  isSkeleton: boolean
  /** The marker on a part still to fill in, where no guided interview asks for it (the vendor
   *  letter, P21); the documents' own marker points to the interview. */
  toFillIn?: string
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const Title = isSkeleton ? 'h2' : 'h1'
  return (
    <article
      aria-label={t('documents.preview')}
      className="flex min-w-0 grow flex-col gap-5 rounded-card border border-white/95 bg-white/90 px-6 py-8 shadow-glass md:px-12 md:py-10"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-5 gap-y-2">
        <Title
          lang={document.language}
          className="m-0 min-w-0 font-serif text-document-title [overflow-wrap:anywhere] hyphens-auto text-ink"
        >
          {document.title}
        </Title>
        <StatusPill status="draft" className="shrink-0" />
      </div>
      <p className="m-0 text-caption text-slate">
        {t('documents.lawLine', {
          version: t(`lawShort.${document.law_version}`),
          date: longDate(document.as_of, language),
        })}
      </p>
      {document.note && (
        <p className="m-0 rounded-card-small px-3.5 py-3 text-caption text-ink-2 glass-thin">
          {document.note}
        </p>
      )}
      {document.sections.map((section) => (
        <Section key={section.key} section={section} isSkeleton={isSkeleton} toFillIn={toFillIn} />
      ))}
      <p className="m-0 mt-auto text-micro text-slate">
        {t('documents.preparedWith')} {document.disclaimer}
      </p>
    </article>
  )
}
