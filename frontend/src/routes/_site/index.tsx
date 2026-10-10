import { createFileRoute } from '@tanstack/react-router'

import { LandingPage } from '@/features/landing/LandingPage'
import { showLanguage } from '@/i18n'

// The English landing page (P16, artboard `Main`): arriving here shows the site in English, as
// arriving at /de shows it in German. The visitor's saved language stays as it was.
export const Route = createFileRoute('/_site/')({
  beforeLoad: () => showLanguage('en'),
  component: LandingPage,
})
