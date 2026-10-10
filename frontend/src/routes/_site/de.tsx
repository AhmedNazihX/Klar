import { createFileRoute } from '@tanstack/react-router'

import { LandingPage } from '@/features/landing/LandingPage'
import { showLanguage } from '@/i18n'

// The German landing page (P16, artboard `MainDE`): arriving here shows the site in German. The
// visitor's saved language stays as it was.
export const Route = createFileRoute('/_site/de')({
  beforeLoad: () => showLanguage('de'),
  component: LandingPage,
})
