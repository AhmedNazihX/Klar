import { useId, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

import { provisionName } from './provision-names'
import { internalControlPoint, isGpaiBased, simplifiedFormFor } from './provider-layout'

/** A side panel of the provider layout: a heading, then its content. */
function SidePanel({
  heading,
  children,
}: {
  heading: ReactNode
  children: ReactNode
}): JSX.Element {
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      padded={false}
      className="flex min-w-0 flex-col gap-3 p-6"
    >
      <h2 id={headingId} className="m-0 text-[18px] leading-snug font-semibold text-ink">
        {heading}
      </h2>
      {children}
    </GlassPanel>
  )
}

/** One relief: what it is, what it means for this tool, and the provision. */
function Relief({
  title,
  body,
  reference,
}: {
  title: ReactNode
  body: ReactNode
  reference: ReactNode
}): JSX.Element {
  return (
    <div className="flex flex-col gap-1.5 rounded-card-small px-3.5 py-3 glass-thin">
      <span className="text-body-small font-semibold text-ink">{title}</span>
      <span className="text-label font-normal text-ink-2">{body}</span>
      <span className="text-caption font-normal text-slate">{reference}</span>
    </div>
  )
}

/**
 * "What makes it lighter": Art. 11(1)'s simplified documentation form for an SME or a small
 * mid-cap (from the company profile's size class; the form isn't published yet), and the
 * internal-control route for an Annex III point 2 to 8 system (Art. 43(2)). Nothing when
 * neither applies.
 */
export function LighterPanel({ result }: { result: ClassificationResult }): JSX.Element | null {
  const { t } = useTranslation()
  const language = useLanguage()
  const shown = useLawVersion()
  const sizeClass = useUserDataOverview().data?.profile?.sizeClass
  const form = simplifiedFormFor(sizeClass, shown, result)
  const point = internalControlPoint(result)
  if (form === null && point === null) return null
  return (
    <SidePanel heading={t('result.provider.lighter.heading')}>
      {form && (
        <Relief
          title={t('result.provider.lighter.formTitle')}
          body={t(`result.provider.lighter.form.${form}`)}
          reference={provisionName('art:11:1', language)}
        />
      )}
      {point && (
        <Relief
          title={t('result.provider.lighter.internalTitle')}
          body={t('result.provider.lighter.internal', { point })}
          reference={t('result.provider.lighter.internalReference')}
        />
      )}
    </SidePanel>
  )
}

/** "You also use it", for a provider that is also the deployer (E8's `also_role`), with a link
 *  to the deployer duties further down when the result lists them (`dutiesId`). */
export function AlsoUsePanel({ dutiesId }: { dutiesId: string | null }): JSX.Element {
  const { t } = useTranslation()
  return (
    <SidePanel heading={t('result.provider.alsoUse.heading')}>
      <p className="m-0 text-label font-normal text-ink-2">{t('result.provider.alsoUse.body')}</p>
      {dutiesId && (
        <a
          href={`#${dutiesId}`}
          className="self-start text-label font-medium text-lens-blue no-underline hover:underline"
        >
          {t('result.provider.alsoUse.link')}
        </a>
      )}
    </SidePanel>
  )
}

/** Decision 026 item 17: a system built on a general-purpose AI model leaves the model's own
 *  duties with its maker. Nothing for any other result. */
export function GpaiNote({ result }: { result: ClassificationResult }): JSX.Element | null {
  const { t } = useTranslation()
  if (!isGpaiBased(result)) return null
  return (
    <p role="note" className="m-0 max-w-[620px] text-body-small text-ink-2">
      {t('result.provider.gpai')}
    </p>
  )
}
