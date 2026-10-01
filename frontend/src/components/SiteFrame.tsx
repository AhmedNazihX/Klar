import type { JSX, ReactNode } from 'react'

import { MistGround } from './MistGround'
import { SiteFooter } from './SiteFooter'
import { SiteNav } from './SiteNav'

/**
 * The frame of every public page (README › Building the screens › Site pages): the MistGround,
 * the floating SiteNav, the page in a 1248 px column, and the SiteFooter. Public pages start no
 * anonymous session: only the app does (AppFrame).
 */
export function SiteFrame({ children }: { children: ReactNode }): JSX.Element {
  return (
    <MistGround className="flex flex-col px-4 pt-28 pb-16 sm:pt-[164px] md:px-[max(48px,calc((100%-1248px)/2))] md:pb-24">
      <SiteNav />
      <main className="flex min-w-0 flex-col gap-8">{children}</main>
      <SiteFooter />
    </MistGround>
  )
}
