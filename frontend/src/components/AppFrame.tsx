import { useLocation, useMatches } from '@tanstack/react-router'
import { useId, useState, type JSX, type KeyboardEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useLoadMotion } from '@/hooks/use-load-motion'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'
import { cn } from '@/lib/utils'

import { AppSidebar } from './AppSidebar'
import { AppTopBar, PhoneTopBar, type LawBinding } from './AppTopBar'
import { LawNotice } from './LawNotice'
import { LAW_ORIGINAL_CLASS, LAW_SCOPE_CLASS } from './LawSwitch'
import { Notice } from './Notice'
import { SessionNotice } from './SessionNotice'

/** The screen title of the deepest route that names one (its `staticData.titleKey`). */
function useScreenTitle(): string {
  const { t } = useTranslation()
  const matches = useMatches()
  const titleKey = matches.findLast((match) => match.staticData.titleKey)?.staticData.titleKey
  return titleKey ? t(titleKey) : ''
}

/**
 * The frame of every app screen (README › Building the screens): 24 px from the window, the 248 px
 * glass sidebar, then the main column with the top bar and its law version switch, the LawNotice
 * under it, the screen, and the closing Notice. Below 768 px the sidebar folds behind a phone top
 * bar's Menu button. Panels settle in reading order on load, and a new screen's panels again on
 * each navigation (index.css › app-load).
 */
export function AppFrame({ law, children }: { law: LawBinding; children: ReactNode }): JSX.Element {
  const { pathname } = useLocation()
  const title = useScreenTitle()
  const motion = useLoadMotion(pathname)
  const menuId = useId()
  const overview = useUserDataOverview()
  // The phone menu belongs to the screen it was opened on, so going anywhere closes it.
  const [menuOpenOn, setMenuOpenOn] = useState<string | null>(null)
  const isMenuOpen = menuOpenOn === pathname

  function closeOnEscape(event: KeyboardEvent): void {
    if (event.key === 'Escape') setMenuOpenOn(null)
  }

  return (
    <div
      onKeyDown={closeOnEscape}
      // The law class is rendered here as well as set by LawSwitch: React rewrites the whole
      // class attribute whenever it changes (the load motion clearing), which would drop a
      // class only the switch had added.
      className={cn(
        LAW_SCOPE_CLASS,
        law.value === 'original' && LAW_ORIGINAL_CLASS,
        'app-frame min-h-dvh px-4 pt-3 pb-6 md:p-6',
        motion.isFrameEntering && 'app-intro',
      )}
    >
      <aside
        id={menuId}
        className={cn(
          'fixed inset-x-4 top-[84px] bottom-4 z-20 flex-col gap-7 overflow-y-auto rounded-panel px-3.5 py-6 glass',
          'md:inset-x-auto md:top-6 md:bottom-6 md:left-6 md:flex md:w-[248px]',
          isMenuOpen ? 'flex' : 'hidden',
        )}
      >
        <AppSidebar company={overview.data?.profile ?? null} />
      </aside>
      <div className="flex min-w-0 flex-col gap-4 md:ml-[272px]">
        <PhoneTopBar
          isMenuOpen={isMenuOpen}
          menuId={menuId}
          onMenuToggle={() => {
            setMenuOpenOn(isMenuOpen ? null : pathname)
          }}
        />
        <main className="app-column flex min-w-0 flex-col gap-5">
          <AppTopBar title={title} law={law} />
          <LawNotice />
          <SessionNotice />
          <div
            className={cn(
              'app-screen flex min-w-0 flex-col gap-5',
              motion.isScreenEntering && 'app-screen-intro',
            )}
          >
            {children}
          </div>
          <Notice className="app-closing" />
        </main>
      </div>
    </div>
  )
}
