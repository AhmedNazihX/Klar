import { createFileRoute } from '@tanstack/react-router'

import { PrivacyPage } from '@/features/site-pages/PrivacyPage'

// The privacy notice (artboard `Privacy`), P17. It shows the site in the visitor's current language.
export const Route = createFileRoute('/_site/privacy')({ component: PrivacyPage })
