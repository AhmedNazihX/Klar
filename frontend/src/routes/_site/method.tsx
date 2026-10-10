import { createFileRoute } from '@tanstack/react-router'

import { MethodPage } from '@/features/site-pages/MethodPage'

// How Klar is measured (artboard `Method`), P17. It shows the site in the visitor's current language.
export const Route = createFileRoute('/_site/method')({ component: MethodPage })
