import type { JSX, ReactNode } from 'react'

/**
 * A label with a shorter form on a phone (below 768 px), e.g. the compact law version switch
 * ("As amended, 2026"). The hidden form is display: none, so it is not read out either.
 */
export function PhoneLabel({ phone, wide }: { phone: ReactNode; wide: ReactNode }): JSX.Element {
  return (
    <>
      <span className="md:hidden">{phone}</span>
      <span className="hidden md:inline">{wide}</span>
    </>
  )
}
