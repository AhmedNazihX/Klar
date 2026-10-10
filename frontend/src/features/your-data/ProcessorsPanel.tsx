import { Link } from '@tanstack/react-router'
import { useId, type JSX } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { PLACEHOLDER_TAGS } from '@/components/placeholder-tags'

// Every processor in the data chain, named (INIT › Ethical considerations; decision 005): the
// models through OpenRouter on Azure EU and Google Vertex EU, embeddings on Nebius, storage on
// Supabase. A check Azure's content filter blocks goes once more to Gemini on Google Vertex EU
// (decision 033). Keep in step with the privacy notice (P17), which reads these same strings; the
// Nebius region stays a marked placeholder until Nebius confirms it (decision 005).
const PROCESSORS = ['models', 'search', 'storage'] as const

/** "Who processes it": what each processor does with the user's text, and the privacy notice. */
export function ProcessorsPanel(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3 p-6.5">
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {t('yourData.who.heading')}
      </h2>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {PROCESSORS.map((processor) => (
          <li key={processor} className="flex flex-col gap-0.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-body-small text-ink">
              <span>{t(`yourData.who.${processor}`)}</span>
              <span className="text-caption text-slate">{t(`yourData.who.${processor}Role`)}</span>
            </div>
            <p className="m-0 text-caption font-normal text-slate">
              <Trans i18nKey={`yourData.who.${processor}Detail`} components={PLACEHOLDER_TAGS} />
            </p>
            {processor === 'models' && (
              <p className="m-0 text-caption font-normal text-slate">
                {t('yourData.who.modelsRefusal')}
              </p>
            )}
          </li>
        ))}
      </ul>
      <p className="m-0 text-caption font-normal text-ink-2">{t('yourData.who.noTraining')}</p>
      <Link
        to="/privacy"
        className="mt-auto self-start rounded-md text-label text-lens-blue hover:underline"
      >
        {t('yourData.who.privacyLink')}
      </Link>
    </GlassPanel>
  )
}
