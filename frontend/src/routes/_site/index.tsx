import { createFileRoute } from '@tanstack/react-router'
import i18n from 'i18next'

import { LandingPage } from '@/features/landing/LandingPage'

// The English landing page (P16, artboard `Main`): arriving here shows the site in English, as
// arriving at /de shows it in German.
export const Route = createFileRoute('/_site/')({
  beforeLoad: async () => {
    if (i18n.resolvedLanguage !== 'en') await i18n.changeLanguage('en')
  },
  component: LandingPage,
})
