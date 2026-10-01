import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P5 (artboards `Classify`, `ClassifyVague`, `ClassifyError`).
export const Route = createFileRoute('/app/classify')({
  component: ClassifyScreen,
  staticData: { titleKey: 'screen.classify' },
})

function ClassifyScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.classify')} />
}
