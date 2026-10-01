import { createFileRoute } from '@tanstack/react-router'

import { HoldingPage } from '@/features/landing/HoldingPage'

// The English landing page (P16, artboard `Main`).
export const Route = createFileRoute('/_site/')({ component: HoldingPage })
