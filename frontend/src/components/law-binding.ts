import { createContext, useContext } from 'react'

import type { LawVersion } from './LawSwitch'

/** The app's law version and how to change it (the `law` search param, routes/app.tsx). */
export type LawBinding = {
  value: LawVersion
  onChange: (value: LawVersion) => void
}

/** The binding AppFrame's own switch uses, for a screen that shows the switch itself (a phone
 *  result, ScreenLawSwitch). */
export const LawBindingContext = createContext<LawBinding | null>(null)

export function useLawBinding(): LawBinding {
  const binding = useContext(LawBindingContext)
  if (!binding) throw new Error('useLawBinding needs an AppFrame around it')
  return binding
}
