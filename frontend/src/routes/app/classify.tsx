import { createFileRoute } from '@tanstack/react-router'

import { ClassifyScreen } from '@/features/classify/ClassifyScreen'

// Describe a tool and run the checks (P5; artboards `Classify`, `ClassifyError`). The follow-up
// questions are P5b's, "Not enough to start" P20's (artboard `ClassifyVague`).
export const Route = createFileRoute('/app/classify')({
  component: ClassifyScreen,
  staticData: { titleKey: 'screen.classify' },
})
