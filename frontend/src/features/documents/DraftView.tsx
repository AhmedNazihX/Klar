import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DraftDocument, DraftSection } from '@/api'
import { Citation } from '@/components/Citation'
import { StatusPill } from '@/components/StatusPill'
import { longDate } from '@/features/classify/dates'
import { citationSource } from '@/features/classify/result-text'
import { useLanguage } from '@/hooks/use-language'
import { cn } from '@/lib/utils'

/** A skeleton section's status beside its heading (artboard `DocSkeleton`). */
function SectionStatusPill({ section }: { section: DraftSection }): JSX.Element {
  const { t } = useTranslation()
  const count = section.unanswered?.length ?? 0
  const label =
    section.status === 'questions'
      ? t('documents.sectionStatus.questions', { count })
      : t(`documents.sectionStatus.${section.status}`)
  return (
    <span
      data-section-status={section.status}
      className={cn(
        'inline-flex min-h-[22px] items-center rounded-pill px-2 text-xs font-semibold whitespace-nowrap',
        section.status === 'drafted' &&
          'bg-risk-minimal-tint text-risk-minimal shadow-[inset_0_0_0_1px_var(--color-risk-minimal-ring)]',
        section.status === 'questions' && 'bg-lens-blue text-white',
        section.status === 'to_fill_in' &&
          'border-[1.5px] border-dashed border-status-info-ring bg-white/60 text-ink-2',
        section.status === 'needs_evidence' &&
          'bg-risk-high-tint text-risk-high shadow-[inset_0_0_0_1px_var(--color-risk-high-ring)]',
        section.status === 'generated_last' &&
          'bg-white/60 text-slate shadow-[inset_0_0_0_1px_var(--color-border-subtle)]',
      )}
    >
      {label}
    </span>
  )
}

function Section({
  section,
  isSkeleton,
}: {
  section: DraftSection
  isSkeleton: boolean
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
    <section aria-label={section.heading} className="flex flex-col gap-2">
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
          {t('documents.toFillIn')}
        </p>
      )}
    </section>
  )
}

/** The document on white (artboards `Documents`, `DocSkeleton`): its title with the DRAFT stamp,
 *  the law version and date, the note, every section, and the notice. User text is shown as
 *  text, never as markup. */
export function DraftView({ document }: { document: DraftDocument }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const isSkeleton = document.sections.some((section) => section.requirement != null)
  return (
    <article
      aria-label={t('documents.preview')}
      className="flex min-w-0 grow flex-col gap-5 rounded-card border border-white/95 bg-white/90 px-6 py-8 shadow-glass md:px-12 md:py-10"
    >
      <div className="flex items-start justify-between gap-5">
        <h1 className="m-0 font-serif text-document-title text-ink">{document.title}</h1>
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
        <Section key={section.key} section={section} isSkeleton={isSkeleton} />
      ))}
      <p className="m-0 mt-auto text-micro text-slate">
        {t('documents.preparedWith')} {document.disclaimer}
      </p>
    </article>
  )
}
