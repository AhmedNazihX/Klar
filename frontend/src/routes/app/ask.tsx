import { createFileRoute } from '@tanstack/react-router'

import { AskScreen } from '@/features/ask/AskScreen'

// Questions about the AI Act, answered with the provisions they rest on (P7, artboard `Ask`).
export const Route = createFileRoute('/app/ask')({
  component: AskScreen,
  staticData: { titleKey: 'screen.ask' },
})
