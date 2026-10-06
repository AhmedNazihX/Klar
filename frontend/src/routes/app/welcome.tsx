import { createFileRoute } from '@tanstack/react-router'

import { WelcomeScreen } from '@/features/welcome/WelcomeScreen'

// The first visit and the company profile (P18, artboard `Welcome`).
export const Route = createFileRoute('/app/welcome')({
  component: WelcomeScreen,
  staticData: { titleKey: 'screen.welcome' },
})
