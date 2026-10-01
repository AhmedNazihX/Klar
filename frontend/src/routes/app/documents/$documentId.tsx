import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P8b (artboard `DocSkeleton`).
export const Route = createFileRoute('/app/documents/$documentId')({
  component: DocumentScreen,
  staticData: { titleKey: 'screen.document' },
})

function DocumentScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.document')} />
}
