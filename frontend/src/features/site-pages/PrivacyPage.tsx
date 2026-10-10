import type { JSX } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { Placeholder } from '@/components/Placeholder'

import { PLACEHOLDER_TAGS } from './placeholder-tags'
import {
  InfoRows,
  InfoSection,
  InfoText,
  PageIntro,
  TemplateNote,
  type InfoRow,
} from './SitePageParts'

function ResponsibleSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = [
    {
      key: 'controller',
      label: t('sitePages.privacy.responsible.controller'),
      text: (
        <Trans
          i18nKey="sitePages.privacy.responsible.controllerText"
          components={PLACEHOLDER_TAGS}
        />
      ),
    },
    {
      key: 'contact',
      label: t('sitePages.privacy.responsible.contact'),
      text: <Placeholder>{t('sitePages.privacy.responsible.contactPh')}</Placeholder>,
    },
    {
      key: 'dpo',
      label: t('sitePages.privacy.responsible.dpo'),
      text: <Placeholder>{t('sitePages.privacy.responsible.dpoPh')}</Placeholder>,
    },
  ]
  return (
    <InfoSection title={t('sitePages.privacy.responsible.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

function PurposesSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = [
    {
      key: 'descriptions',
      label: t('sitePages.privacy.purposes.descriptions'),
      text: (
        <Trans
          i18nKey="sitePages.privacy.purposes.descriptionsText"
          components={PLACEHOLDER_TAGS}
        />
      ),
    },
    {
      key: 'questions',
      label: t('sitePages.privacy.purposes.questions'),
      text: t('sitePages.privacy.purposes.questionsText'),
    },
    {
      key: 'logs',
      label: t('sitePages.privacy.purposes.logs'),
      text: <Trans i18nKey="sitePages.privacy.purposes.logsText" components={PLACEHOLDER_TAGS} />,
    },
    {
      key: 'never',
      label: t('sitePages.privacy.purposes.never'),
      text: t('sitePages.privacy.purposes.neverText'),
    },
  ]
  return (
    <InfoSection title={t('sitePages.privacy.purposes.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

/** What is stored, and the 30 days (decision 013); questions to Klar stay in the browser (026 item 6). */
function KeptSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = (['stored', 'questions', 'retention'] as const).map((key) => ({
    key,
    label: t(`sitePages.privacy.kept.${key}`),
    text: t(`sitePages.privacy.kept.${key}Text`),
  }))
  return (
    <InfoSection title={t('sitePages.privacy.kept.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

/**
 * Every processor, named (INIT › Ethical considerations; decision 005). The model lines are the
 * Your data panel's own strings (yourData.who.*), so the two can't drift apart; the refusal route
 * is decision 033's wording, word for word.
 */
function ProcessorsSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = [
    {
      key: 'models',
      label: t('sitePages.privacy.processors.models'),
      text: (
        <span className="flex flex-col gap-2">
          <span>{t('yourData.who.modelsDetail')}</span>
          <span>{t('yourData.who.modelsRefusal')}</span>
          <span>{t('yourData.who.noTraining')}</span>
        </span>
      ),
    },
    {
      key: 'search',
      label: t('sitePages.privacy.processors.search'),
      // One string with the Your data panel, so the region claim changes in one place (decision 005).
      text: <Trans i18nKey="yourData.who.searchDetail" components={PLACEHOLDER_TAGS} />,
    },
    {
      key: 'storage',
      label: t('sitePages.privacy.processors.storage'),
      text: (
        <Trans i18nKey="sitePages.privacy.processors.storageText" components={PLACEHOLDER_TAGS} />
      ),
    },
    {
      key: 'transfers',
      label: t('sitePages.privacy.processors.transfers'),
      text: <Placeholder>{t('sitePages.privacy.processors.transfersPh')}</Placeholder>,
    },
  ]
  return (
    <InfoSection title={t('sitePages.privacy.processors.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

/**
 * The privacy notice (artboard `Privacy`, decision 026 items 5–7, 9 and C3): a template whose
 * unknowns are marked placeholders, with the decided values filled in: 30 days without activity,
 * what Klar keeps, and the named processors.
 */
export function PrivacyPage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <PageIntro title={t('site.page.privacy')} lead={t('sitePages.privacy.lead')} />
      <TemplateNote>{t('sitePages.privacy.template')}</TemplateNote>
      <ResponsibleSection />
      <PurposesSection />
      <KeptSection />
      <ProcessorsSection />
      <InfoSection title={t('sitePages.privacy.rights.title')}>
        <InfoText>
          <Trans i18nKey="sitePages.privacy.rights.text" components={PLACEHOLDER_TAGS} />
        </InfoText>
      </InfoSection>
    </>
  )
}
