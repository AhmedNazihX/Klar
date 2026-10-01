import type { IconName } from './icon-files'

/** The app's five places, in the sidebar's order. A link is active on its own path and below it. */
export const APP_NAV_ITEMS = [
  { to: '/app/inventory', icon: 'inventory', labelKey: 'nav.inventory' },
  { to: '/app/classify', icon: 'classify', labelKey: 'nav.classify' },
  { to: '/app/obligations', icon: 'obligations', labelKey: 'nav.obligations' },
  { to: '/app/documents', icon: 'documents', labelKey: 'nav.documents' },
  { to: '/app/ask', icon: 'ask', labelKey: 'nav.ask' },
] as const satisfies readonly { to: string; icon: IconName; labelKey: `nav.${string}` }[]

// Labels must fit 220 px at 15 px (localisation.md). An item is 220 px wide (the 248 px sidebar
// less its 14 px padding each side); its own 14 px padding each side, the 18 px icon and the 12 px
// gap leave 162 px for the label. Geist at 15 px averages under 9 px a character even in wide
// words, so 18 characters always fit. SidebarNav.browser.test.tsx measures the real widths too.
export const SIDEBAR_ITEM_WIDTH_PX = 220
export const SIDEBAR_LABEL_MAX_CHARS = 18
