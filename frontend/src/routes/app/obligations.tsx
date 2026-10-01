import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P24 (artboard `Obligations`).
export const Route = createFileRoute('/app/obligations')({
  component: ObligationsScreen,
  staticData: { titleKey: 'screen.obligations' },
})

function ObligationsScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.obligations')} />
}
