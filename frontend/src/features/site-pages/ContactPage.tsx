import { Link } from '@tanstack/react-router'
import { useId, useState, type JSX } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { Placeholder } from '@/components/Placeholder'
import { PLACEHOLDER_TAGS } from '@/components/placeholder-tags'
import { Reveal } from '@/components/Reveal'
import { SegmentedControl } from '@/components/SegmentedControl'

import { CONTACT_ADDRESS, CONTACT_TOPICS, contactMailto, type ContactTopic } from './contact-mail'
import { PageIntro } from './SitePageParts'

// The side panels arrive one stagger step (the 110 ms token) after another.
const STAGGER_MS = 110
// Three topics don't fit side by side on a phone ("Datenschutzanfrage"), so below md they stack,
// full width, each still a 44 px target; the corners follow the 22 px buttons inside 3 px padding.
const TOPIC_STACK_CLASS = 'max-md:flex max-md:w-full max-md:flex-col max-md:rounded-[25px]'
const SIDE_LINK_CLASS = 'self-start rounded-md text-label text-lens-blue hover:underline'

/** The topic, the address and the link that opens an email with the topic as its subject. */
function WritePanel(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const [topic, setTopic] = useState<ContactTopic>('question')
  const href = contactMailto(CONTACT_ADDRESS, t(`sitePages.contact.subject.${topic}`))
  return (
    <Reveal className="min-w-0 flex-1">
      <GlassPanel
        as="section"
        radius="panel"
        aria-labelledby={headingId}
        className="flex flex-col gap-5 md:px-10 md:py-9"
      >
        <h2 id={headingId} className="m-0 text-heading-panel text-ink">
          {t('sitePages.contact.write.title')}
        </h2>
        <div className="flex flex-col gap-2">
          <span className="text-label font-semibold text-ink">
            {t('sitePages.contact.write.topic')}
          </span>
          <SegmentedControl<ContactTopic>
            label={t('sitePages.contact.write.topic')}
            value={topic}
            onChange={setTopic}
            options={CONTACT_TOPICS.map((value) => ({
              value,
              label: t(`sitePages.contact.write.${value}`),
            }))}
            className={TOPIC_STACK_CLASS}
          />
        </div>
        <p className="m-0 text-body-small text-ink-2">
          <span className="font-semibold text-ink">{t('sitePages.contact.write.address')}</span>{' '}
          {CONTACT_ADDRESS ?? <Placeholder>{t('sitePages.contact.write.addressPh')}</Placeholder>}
        </p>
        <p className="m-0 text-label font-normal text-slate">{t('sitePages.contact.write.how')}</p>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span className="text-caption font-normal text-slate">
            {t('sitePages.contact.write.personal')}
          </span>
          <a href={href} className={buttonVariants({ size: 'md' })}>
            {t('sitePages.contact.write.send')}
          </a>
        </div>
      </GlassPanel>
    </Reveal>
  )
}

function SidePanels(): JSX.Element {
  const { t } = useTranslation()
  const legalId = useId()
  const privacyId = useId()
  return (
    <div className="flex flex-col gap-5 lg:w-[380px] lg:shrink-0">
      <Reveal delay={STAGGER_MS}>
        <GlassPanel as="section" aria-labelledby={legalId} className="flex flex-col gap-2.5 p-6.5">
          <h2 id={legalId} className="m-0 text-heading-small text-ink">
            {t('sitePages.contact.legal.title')}
          </h2>
          <p className="m-0 text-body-small text-ink-2">{t('sitePages.contact.legal.text')}</p>
          <Link to="/app/ask" className={SIDE_LINK_CLASS}>
            {t('sitePages.contact.legal.link')}
          </Link>
        </GlassPanel>
      </Reveal>
      <Reveal delay={2 * STAGGER_MS}>
        <GlassPanel
          as="section"
          aria-labelledby={privacyId}
          className="flex flex-col gap-2.5 p-6.5"
        >
          <h2 id={privacyId} className="m-0 text-heading-small text-ink">
            {t('sitePages.contact.privacy.title')}
          </h2>
          <p className="m-0 text-body-small text-ink-2">
            <Trans
              i18nKey="sitePages.contact.privacy.text"
              components={{
                ...PLACEHOLDER_TAGS,
                yourData: <Link to="/app/your-data" className="text-lens-blue hover:underline" />,
              }}
            />
          </p>
        </GlassPanel>
      </Reveal>
    </div>
  )
}

/**
 * Contact (artboard `Contact`, decision 026 item 5): no form backend. The drawn form becomes a
 * topic switch and a `mailto:` link with the topic as its subject; the address is a marked
 * placeholder until it is decided (CONTACT_ADDRESS).
 */
export function ContactPage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <PageIntro
        title={t('site.page.contact')}
        lead={<Trans i18nKey="sitePages.contact.lead" components={PLACEHOLDER_TAGS} />}
      />
      <div className="flex flex-col items-stretch gap-6 lg:flex-row lg:items-start">
        <WritePanel />
        <SidePanels />
      </div>
    </>
  )
}
