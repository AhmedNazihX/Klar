import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P18 (artboard `Welcome`).
export const Route = createFileRoute('/app/welcome')({
  component: WelcomeScreen,
  staticData: { titleKey: 'screen.welcome' },
})

function WelcomeScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.welcome')} />
}
