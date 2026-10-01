import type { IconName } from './icon-files'

/** The app's five places, in the sidebar's order. A link is active on its own path and below it. */
export const APP_NAV_ITEMS = [
  { to: '/app/inventory', icon: 'inventory', labelKey: 'nav.inventory' },
  { to: '/app/classify', icon: 'classify', labelKey: 'nav.classify' },
  { to: '/app/obligations', icon: 'obligations', labelKey: 'nav.obligations' },
  { to: '/app/documents', icon: 'documents', labelKey: 'nav.documents' },
  { to: '/app/ask', icon: 'ask', labelKey: 'nav.ask' },
] as const satisfies readonly { to: string; icon: IconName; labelKey: `nav.${string}` }[]

// Labels must fit 220 px at 15 px (localisation.md): an item is at most the 248 px sidebar less
// its 14 px padding each side. shells.browser.test.tsx measures every label in EN and DE.
export const SIDEBAR_ITEM_WIDTH_PX = 220
