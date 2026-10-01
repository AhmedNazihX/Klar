import { createFileRoute, Outlet } from '@tanstack/react-router'
import type { JSX } from 'react'

import { SiteFrame } from '@/components/SiteFrame'

/** The public pages' frame: MistGround, SiteNav and SiteFooter around each page. */
export const Route = createFileRoute('/_site')({ component: SiteLayout })

function SiteLayout(): JSX.Element {
  return (
    <SiteFrame>
      <Outlet />
    </SiteFrame>
  )
}
