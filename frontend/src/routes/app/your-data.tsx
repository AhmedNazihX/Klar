import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P12 (artboard `YourData`).
export const Route = createFileRoute('/app/your-data')({
  component: YourDataScreen,
  staticData: { titleKey: 'screen.yourData' },
})

function YourDataScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.yourData')} />
}
