import { createFileRoute } from '@tanstack/react-router'

import { YourDataScreen } from '@/features/your-data/YourDataScreen'

// What Klar keeps, who processes it, download, import and delete (P12, artboard `YourData`).
export const Route = createFileRoute('/app/your-data')({
  component: YourDataScreen,
  staticData: { titleKey: 'screen.yourData' },
})
