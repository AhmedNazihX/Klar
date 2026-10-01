import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenPlaceholder } from '@/components/ScreenPlaceholder'

// Empty until P6 (artboard `Inventory`).
export const Route = createFileRoute('/app/inventory/')({
  component: InventoryScreen,
  staticData: { titleKey: 'screen.inventory' },
})

function InventoryScreen(): JSX.Element {
  const { t } = useTranslation()
  return <ScreenPlaceholder title={t('screen.inventory')} />
}
