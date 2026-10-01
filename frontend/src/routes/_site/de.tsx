import { createFileRoute } from '@tanstack/react-router'
import i18n from 'i18next'

import { HoldingPage } from '@/features/landing/HoldingPage'

// The German landing page (P16, artboard `MainDE`): arriving here shows the site in German.
export const Route = createFileRoute('/_site/de')({
  beforeLoad: async () => {
    if (i18n.resolvedLanguage !== 'de') await i18n.changeLanguage('de')
  },
  component: HoldingPage,
})
