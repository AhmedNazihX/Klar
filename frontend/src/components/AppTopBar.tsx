import { Link } from '@tanstack/react-router'
import { useRef, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { KlarLogo } from './KlarLogo'
import { useLawBinding, type LawBinding } from './law-binding'
import { LawSwitch } from './LawSwitch'
import { MenuMark } from './MenuMark'
import { PhoneLabel } from './PhoneLabel'

/** Marks a screen's own law switch: on a phone the top bar gives way to it
 *  (index.css › app-top-bar). */
const SCREEN_LAW_SWITCH_CLASS = 'screen-law-switch'

/**
 * The bar over every app screen: where you are on the left, the law version switch on the right.
 * On a phone the switch is compact (as amended, 2026), and the visible "Law version" label goes.
 * A screen that places the switch itself on a phone (ScreenLawSwitch) hides this bar there.
 */
export function AppTopBar({ title, law }: { title: string; law: LawBinding }): JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="app-top-bar flex min-h-13 flex-wrap items-center justify-between gap-x-4 gap-y-2">
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

/**
 * The compact law switch inside a screen, for a phone only (artboard `ResultMobile`: under the
 * title; the screen renders it when useIsPhone says so). It drives the same `law` param as the
 * top bar's switch, which stays the one that marks the frame: this one's own class toggle is kept
 * to its wrapper.
 */
export function ScreenLawSwitch(): JSX.Element {
  const { t } = useTranslation()
  const law = useLawBinding()
  const ownScope = useRef<HTMLDivElement>(null)
  return (
    <div ref={ownScope} className={`${SCREEN_LAW_SWITCH_CLASS} flex`}>
      <LawSwitch
        scope={ownScope}
        value={law.value}
        onChange={law.onChange}
        amendedLabel={t('lawShort.amended')}
        originalLabel={t('lawShort.original')}
      />
    </div>
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
    // A header (the banner landmark), so the logo and Menu sit in a landmark like the rest.
    <header className="flex h-14 items-center justify-between rounded-pill pr-2 pl-4.5 glass md:hidden">
      <Link to="/app" aria-label={t('app.home')} className="flex h-11 items-center rounded-md">
        <KlarLogo className="h-[26px] w-auto" />
      </Link>
      <button
        type="button"
        aria-label={t('sidebar.menu')}
        aria-expanded={isMenuOpen}
        aria-controls={menuId}
        onClick={onMenuToggle}
        className="flex size-11 cursor-pointer items-center justify-center rounded-full bg-white/60 text-ink"
      >
        <MenuMark />
      </button>
    </header>
  )
}
