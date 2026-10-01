import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P5 (artboards `Result`, `Reviewer`, `ResultNeedsInfo`, `ResultRerun`, `ResultAmbiguous`, `ResultProhibited`, `ResultProvider`, `ResultDE`, `ResultMobile`).
export const Route = createFileRoute('/app/inventory/$toolId')({
  component: ResultScreen,
  staticData: { titleKey: 'screen.result' },
})

function ResultScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.result')} />
}
