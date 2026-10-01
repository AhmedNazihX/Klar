import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { APP_NAV_ITEMS } from './app-nav'
import { Icon } from './Icon'

/** The app's main navigation in the glass sidebar. The active item is white glass, aria-current. */
export function SidebarNav(): JSX.Element {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('nav.label')} className="flex flex-col gap-1">
      {APP_NAV_ITEMS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className="flex h-11 items-center gap-3 rounded-item px-3.5 text-body-small font-medium whitespace-nowrap text-ink-2 no-underline transition-[background-color,box-shadow,color] duration-250 ease-settle hover:bg-white/45 hover:text-ink aria-[current=page]:bg-white/82 aria-[current=page]:font-semibold aria-[current=page]:text-ink aria-[current=page]:shadow-item-active"
        >
          <Icon name={item.icon} />
          <span data-sidebar-label>{t(item.labelKey)}</span>
        </Link>
      ))}
    </nav>
  )
}
