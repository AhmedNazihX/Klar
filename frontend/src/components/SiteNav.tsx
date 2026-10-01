import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { Language } from '@/i18n'
import { cn } from '@/lib/utils'

import { buttonVariants } from './button-variants'
import { KlarLogo } from './KlarLogo'
import { LanguageSwitch } from './LanguageSwitch'
import { LANDING_PATH, landingPathFor } from './site-paths'

const LINK_CLASS =
  'relative text-[15px] font-medium text-ink no-underline after:absolute after:inset-x-0 after:-bottom-[7px] after:h-0.5 after:origin-left after:scale-x-0 after:rounded-full after:bg-lens-blue after:transition-transform after:duration-300 after:ease-settle hover:text-lens-blue hover:after:scale-x-100 focus-visible:after:scale-x-100'

// A section link is active only on its own section, not on the whole landing page.
const HASH_ACTIVE = { includeHash: true } as const

/**
 * The public pages' navigation (components.md › SiteNav): one floating glass pill with the logo,
 * four links, the EN/DE switch and the one action. The four links need a wide screen; below
 * 1024 px the pill keeps the logo, the switch and the action. On a landing page the switch also
 * moves to the other language's landing page.
 */
export function SiteNav(): JSX.Element {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const landing = landingPathFor(i18n.resolvedLanguage)
  const isOnLanding = pathname === LANDING_PATH.en || pathname === LANDING_PATH.de

  function followLanguage(language: Language): void {
    if (isOnLanding) void navigate({ to: LANDING_PATH[language] })
  }

  return (
    <nav
      aria-label={t('site.navLabel')}
      className="absolute inset-x-4 top-4 z-10 flex h-16 items-center justify-between gap-4 rounded-pill pr-2 pl-4 glass sm:top-6 sm:h-[68px] sm:pr-3 sm:pl-6.5 lg:inset-x-[max(48px,calc((100%-1344px)/2))]"
    >
      <Link
        to={landing}
        aria-label={t('app.home')}
        className="flex h-11 shrink-0 items-center rounded-md"
      >
        <KlarLogo className="h-7 w-auto sm:h-9" />
      </Link>
      <div className="hidden gap-8 lg:flex">
        <Link to={landing} hash="how" activeOptions={HASH_ACTIVE} className={LINK_CLASS}>
          {t('site.how')}
        </Link>
        <Link to={landing} hash="accuracy" activeOptions={HASH_ACTIVE} className={LINK_CLASS}>
          {t('site.accuracy')}
        </Link>
        <Link to={landing} hash="agents" activeOptions={HASH_ACTIVE} className={LINK_CLASS}>
          {t('site.agents')}
        </Link>
        <Link to="/privacy" className={LINK_CLASS}>
          {t('site.yourData')}
        </Link>
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <LanguageSwitch onChange={followLanguage} />
        <Link to="/app" className={cn(buttonVariants({ size: 'sm' }), 'text-white')}>
          {t('site.classify')}
        </Link>
      </div>
    </nav>
  )
}
