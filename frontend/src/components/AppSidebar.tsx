import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { CompanyProfile } from '@/lib/company-profile'

import { CompanyLine } from './CompanyLine'
import { KlarLogo } from './KlarLogo'
import { LanguageSwitch } from './LanguageSwitch'
import { SidebarNav } from './SidebarNav'

/**
 * What the glass sidebar holds, top to bottom: the logo, the five places, the company line, then
 * at the foot the language switch, the AI and guidance notice and the two data links.
 * The company line is filled from the company profile, and says when there is none yet.
 */
export function AppSidebar({ company }: { company: CompanyProfile | null }): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      {/* Exact: every /app/* route starts with /app, and the logo isn't the page you're on. */}
      <Link
        to="/app"
        activeOptions={{ exact: true }}
        aria-label={t('app.home')}
        className="mt-1.5 ml-3.5 flex self-start rounded-md"
      >
        <KlarLogo className="h-[34px] w-auto" />
      </Link>
      <SidebarNav />
      <CompanyLine company={company} />
      <div className="mt-auto flex flex-col gap-3.5 px-2">
        <LanguageSwitch className="self-start" />
        <p className="text-micro text-slate">{t('app.notice')}</p>
        <div className="flex flex-wrap gap-x-3.5 gap-y-1.5 text-caption">
          <Link to="/app/your-data" className="text-ink-2 hover:underline">
            {t('sidebar.exportData')}
          </Link>
          <Link to="/app/your-data" className="text-risk-prohibited hover:underline">
            {t('sidebar.deleteData')}
          </Link>
        </div>
      </div>
    </>
  )
}
