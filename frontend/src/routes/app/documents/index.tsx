import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P8a (artboard `Documents`).
export const Route = createFileRoute('/app/documents/')({
  component: DocumentsScreen,
  staticData: { titleKey: 'screen.documents' },
})

function DocumentsScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.documents')} />
}
