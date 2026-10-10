import { createFileRoute } from '@tanstack/react-router'

import { ImpressumPage } from '@/features/site-pages/ImpressumPage'

// The Impressum (artboard `Impressum`), P17. It shows the site in the visitor's current language.
export const Route = createFileRoute('/_site/impressum')({ component: ImpressumPage })
