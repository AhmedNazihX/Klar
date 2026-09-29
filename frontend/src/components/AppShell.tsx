import { Link } from '@tanstack/react-router'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { KlarLogo } from '@/components/KlarLogo'
import { LanguageSwitch } from '@/components/LanguageSwitch'
import { useAnonymousSession } from '@/hooks/use-anonymous-session'

/** The page frame: logo and language switch on top, the AI and legal-advice notice at the foot. */
export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const { t } = useTranslation()
  // Every visitor gets an anonymous session on arrival (INIT › Storage).
  useAnonymousSession()
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-5 sm:px-8">
        <Link to="/" aria-label={t('app.home')} className="rounded-md">
          <KlarLogo className="h-8 w-auto" />
        </Link>
        <LanguageSwitch />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-12 sm:px-8">{children}</main>
      <footer className="mx-auto w-full max-w-6xl px-4 pb-8 text-xs leading-relaxed text-muted-foreground sm:px-8">
        <p>{t('app.notice')}</p>
      </footer>
    </div>
  )
}
