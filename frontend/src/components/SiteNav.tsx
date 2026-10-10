import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { useMotionMoment } from '@/hooks/use-motion-moment'
import { useScrolled } from '@/hooks/use-scrolled'
import type { Language } from '@/i18n'
import { cn } from '@/lib/utils'

import { buttonVariants } from './button-variants'
import { KlarLogo } from './KlarLogo'
import { LanguageSwitch } from './LanguageSwitch'
import { MenuMark } from './MenuMark'
import { LANDING_PATH, landingPathFor } from './site-paths'

const LINK_CLASS =
  'relative text-[15px] font-medium text-ink no-underline after:absolute after:inset-x-0 after:-bottom-[7px] after:h-0.5 after:origin-left after:scale-x-0 after:rounded-full after:bg-lens-blue after:transition-transform after:duration-300 after:ease-settle hover:text-lens-blue hover:after:scale-x-100 focus-visible:after:scale-x-100'
const MENU_LINK_CLASS =
  'flex min-h-11 items-center rounded-item px-4 text-[15px] font-medium text-ink no-underline hover:bg-white/60 hover:text-lens-blue'

// A section link is active only on its own section, not on the whole landing page.
const HASH_ACTIVE = { includeHash: true } as const
/** Past this many pixels of scrolling the nav turns denser (the canvas note's 40 px). */
export const NAV_DENSE_AFTER_PX = 40
/** On arriving at the German landing page, the pill waits this long under EN, then flows to DE. */
export const ARRIVAL_FLOW_DELAY_MS = 450

type SectionLink = { key: 'how' | 'accuracy' | 'agents'; hash: string }
const SECTION_LINKS: readonly SectionLink[] = [
  { key: 'how', hash: 'how' },
  { key: 'accuracy', hash: 'accuracy' },
  { key: 'agents', hash: 'agents' },
]

/** The four links: the landing page's three sections by hash, then the privacy page. */
function NavLinks({
  landing,
  className,
  onFollow,
}: {
  landing: (typeof LANDING_PATH)[Language]
  className: string
  onFollow?: () => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      {SECTION_LINKS.map(({ key, hash }) => (
        <Link
          key={key}
          to={landing}
          hash={hash}
          activeOptions={HASH_ACTIVE}
          className={className}
          onClick={onFollow}
        >
          {t(`site.${key}`)}
        </Link>
      ))}
      <Link to="/privacy" className={className} onClick={onFollow}>
        {t('site.yourData')}
      </Link>
    </>
  )
}

/**
 * The public pages' navigation (components.md › SiteNav): one floating glass pill with the logo,
 * four links, the EN/DE switch and the one action. It stays pinned on top and turns denser once the
 * page scrolls. Below 1024 px the four links move into a Sections menu, and below 640 px the
 * action joins them there. On a landing page the switch also moves to the other language's page,
 * and on arriving at the German one the pill flows from EN to DE.
 */
export function SiteNav(): JSX.Element {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const landing = landingPathFor(i18n.resolvedLanguage)
  const isOnLanding = pathname === LANDING_PATH.en || pathname === LANDING_PATH.de
  const isDense = useScrolled(NAV_DENSE_AFTER_PX)
  // On arriving at the German landing page the pill sits under EN for a moment, then flows to DE.
  const isArriving = useMotionMoment(ARRIVAL_FLOW_DELAY_MS, pathname === LANDING_PATH.de)
  const [isMenuOpen, setMenuOpen] = useState(false)
  const menuId = useId()

  function followLanguage(language: Language): void {
    if (isOnLanding) void navigate({ to: LANDING_PATH[language] })
  }

  function closeMenu(): void {
    setMenuOpen(false)
  }

  return (
    <nav
      aria-label={t('site.navLabel')}
      data-dense={isDense ? 'true' : undefined}
      className="site-nav fixed inset-x-4 top-4 z-10 flex h-16 items-center justify-between gap-3 rounded-pill pr-2 pl-4 glass sm:top-6 sm:h-[68px] sm:pr-3 sm:pl-6.5 lg:inset-x-[max(48px,calc((100%-1344px)/2))]"
      onKeyDown={(event) => {
        if (event.key === 'Escape') closeMenu()
      }}
    >
      <Link
        to={landing}
        aria-label={t('app.home')}
        className="flex h-11 shrink-0 items-center rounded-md"
      >
        <KlarLogo className="h-7 w-auto sm:h-9" />
      </Link>
      <div className="hidden gap-8 lg:flex">
        <NavLinks landing={landing} className={LINK_CLASS} />
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <LanguageSwitch onChange={followLanguage} shown={isArriving ? 'en' : undefined} />
        <Link
          to="/app"
          className={cn(buttonVariants({ size: 'sm' }), 'hidden text-white sm:inline-flex')}
        >
          {t('site.classify')}
        </Link>
        <button
          type="button"
          aria-label={isMenuOpen ? t('site.menuClose') : t('site.menu')}
          aria-expanded={isMenuOpen}
          aria-controls={menuId}
          onClick={() => {
            setMenuOpen((isOpen) => !isOpen)
          }}
          className="flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full bg-white/60 text-ink lg:hidden"
        >
          <MenuMark />
        </button>
      </div>
      {isMenuOpen && (
        <div
          id={menuId}
          className="absolute inset-x-0 top-[calc(100%+8px)] flex flex-col gap-1 rounded-card p-2 glass lg:hidden"
        >
          <NavLinks landing={landing} className={MENU_LINK_CLASS} onFollow={closeMenu} />
          <Link
            to="/app"
            onClick={closeMenu}
            className={cn(buttonVariants({ size: 'md' }), 'mt-1 text-white sm:hidden')}
          >
            {t('site.classify')}
          </Link>
        </div>
      )}
    </nav>
  )
}
