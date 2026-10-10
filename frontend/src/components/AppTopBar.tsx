import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { KlarLogo } from './KlarLogo'
import { LawSwitch, type LawVersion } from './LawSwitch'
import { PhoneLabel } from './PhoneLabel'

export type LawBinding = {
  value: LawVersion
  onChange: (value: LawVersion) => void
}

/**
 * The bar over every app screen: where you are on the left, the law version switch on the right.
 * On a phone the switch is compact (as amended, 2026), and the visible "Law version" label goes.
 */
export function AppTopBar({ title, law }: { title: string; law: LawBinding }): JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-13 flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <p className="text-label font-normal text-slate">{title}</p>
      <div className="flex shrink-0 items-center gap-2.5">
        <span aria-hidden="true" className="hidden text-caption font-normal text-slate sm:inline">
          {t('law.label')}
        </span>
        <LawSwitch
          value={law.value}
          onChange={law.onChange}
          amendedLabel={<PhoneLabel phone={t('lawShort.amended')} wide={t('law.amended')} />}
          originalLabel={<PhoneLabel phone={t('lawShort.original')} wide={t('law.original')} />}
        />
      </div>
    </div>
  )
}

// The three-line menu mark from the ResultMobile artboard; the system's icon set has none.
export function MenuMark(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  )
}

/** The phone's top bar (below 768 px): the logo and a Menu button that opens the sidebar. */
export function PhoneTopBar({
  isMenuOpen,
  menuId,
  onMenuToggle,
}: {
  isMenuOpen: boolean
  menuId: string
  onMenuToggle: () => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="flex h-14 items-center justify-between rounded-pill pr-2 pl-4.5 glass md:hidden">
      <Link to="/app" aria-label={t('app.home')} className="flex rounded-md">
        <KlarLogo className="h-[26px] w-auto" />
      </Link>
      <button
        type="button"
        aria-label={t('sidebar.menu')}
        aria-expanded={isMenuOpen}
        aria-controls={menuId}
        onClick={onMenuToggle}
        className="flex size-10 cursor-pointer items-center justify-center rounded-full bg-white/60 text-ink"
      >
        <MenuMark />
      </button>
    </div>
  )
}
