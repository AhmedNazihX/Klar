import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P17 (artboard `Impressum`).
export const Route = createFileRoute('/_site/impressum')({ component: ImpressumPage })

function ImpressumPage(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('site.page.impressum')} />
}
