import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'

import { InventoryScreen } from '@/features/inventory/InventoryScreen'

// The AI inventory (P6; artboard `Inventory`). Every row opens its tool's result at
// /app/inventory/$toolId.
export const Route = createFileRoute('/app/inventory/')({
  component: InventoryRoute,
  staticData: { titleKey: 'screen.inventory' },
})

function InventoryRoute(): JSX.Element {
  return <InventoryScreen today={new Date()} />
}
