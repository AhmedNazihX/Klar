import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Placeholder } from '@/components/Placeholder'

import { InfoRows, InfoSection, InfoText, PageIntro, TemplateNote } from './SitePageParts'

// The Impressum's own fields, by section: a German legal notice, so its body is German in both
// languages (the same strings in en.json and de.json), marked lang="de".
const SECTIONS = [
  { title: 'providerTitle', fields: ['name', 'address', 'representedBy'] },
  { title: 'contactTitle', fields: ['email', 'phone'] },
  { title: 'moreTitle', fields: ['vatId', 'register', 'responsible'] },
] as const

/** The Impressum (artboard `Impressum`, § 5 DDG): every field a marked placeholder until launch. */
export function ImpressumPage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <PageIntro lang="de" title={t('site.page.impressum')} lead={t('sitePages.impressum.lead')} />
      <TemplateNote>{t('sitePages.impressum.template')}</TemplateNote>
      {SECTIONS.map(({ title, fields }) => (
        <InfoSection key={title} lang="de" title={t(`sitePages.impressum.body.${title}`)}>
          <InfoRows
            rows={fields.map((field) => ({
              key: field,
              label: t(`sitePages.impressum.body.${field}`),
              text: <Placeholder>{t(`sitePages.impressum.body.${field}Ph`)}</Placeholder>,
            }))}
          />
        </InfoSection>
      ))}
      <InfoSection lang="de" title={t('sitePages.impressum.body.noteTitle')}>
        <InfoText>{t('sitePages.impressum.body.note')}</InfoText>
      </InfoSection>
    </>
  )
}
