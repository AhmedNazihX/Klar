import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { KlarLogo } from './KlarLogo'
import { LanguageSwitch } from './LanguageSwitch'
import { SidebarNav } from './SidebarNav'

/**
 * What the glass sidebar holds, top to bottom: the logo, the five places, the company line, then
 * at the foot the language switch, the AI and guidance notice and the two data links.
 * Until P18 fills it from the company profile, the company line says there is none yet.
 */
export function AppSidebar(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <Link
        to="/app"
        aria-label={t('app.home')}
        className="mt-1.5 ml-3.5 flex self-start rounded-md"
      >
        <KlarLogo className="h-[34px] w-auto" />
      </Link>
      <SidebarNav />
      <div className="flex flex-col gap-1 rounded-[18px] px-4 py-3.5 glass-thin">
        <p className="text-label font-semibold text-ink">{t('sidebar.companyName')}</p>
        <p className="text-caption font-normal text-slate">{t('sidebar.companyEmpty')}</p>
      </div>
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
