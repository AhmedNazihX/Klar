import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P7 (artboard `Ask`).
export const Route = createFileRoute('/app/ask')({
  component: AskScreen,
  staticData: { titleKey: 'screen.ask' },
})

function AskScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.ask')} />
}
