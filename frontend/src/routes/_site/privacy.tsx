import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P17 (artboard `Privacy`).
export const Route = createFileRoute('/_site/privacy')({ component: PrivacyPage })

function PrivacyPage(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('site.page.privacy')} />
}
