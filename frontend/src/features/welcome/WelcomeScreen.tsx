import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon'
import { ScreenTitle } from '@/components/ScreenTitle'

import { CompanyProfileForm } from './CompanyProfileForm'
import { HowItWorks } from './HowItWorks'
import { ToolsPanel } from './ToolsPanel'

/**
 * The first visit (artboard `Welcome`): the heading, "About your company" beside "Your AI tools",
 * "How it works" and the retention note (decision 013: 30 days). One column on a phone.
 */
export function WelcomeScreen(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <div className="flex max-w-[760px] flex-col gap-2.5">
        <ScreenTitle>{t('welcome.title')}</ScreenTitle>
        <p className="m-0 text-body-large text-slate">{t('welcome.intro')}</p>
      </div>
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <CompanyProfileForm />
        <div className="flex min-w-0 flex-col gap-5 xl:w-[380px] xl:shrink-0">
          <ToolsPanel />
          <HowItWorks />
          <p className="m-0 flex items-start gap-2.5 rounded-[18px] px-4 py-3.5 text-caption text-ink-2 glass-thin">
            <Icon name="privacy" size={16} className="mt-0.5" />
            <span>{t('welcome.retention')}</span>
          </p>
        </div>
      </div>
    </>
  )
}
