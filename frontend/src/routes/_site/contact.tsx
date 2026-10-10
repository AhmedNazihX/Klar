import { createFileRoute } from '@tanstack/react-router'

import { ContactPage } from '@/features/site-pages/ContactPage'

// Contact (artboard `Contact`), P17. It shows the site in the visitor's current language.
export const Route = createFileRoute('/_site/contact')({ component: ContactPage })
