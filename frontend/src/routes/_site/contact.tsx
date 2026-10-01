import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P17 (artboard `Contact`).
export const Route = createFileRoute('/_site/contact')({ component: ContactPage })

function ContactPage(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('site.page.contact')} />
}
