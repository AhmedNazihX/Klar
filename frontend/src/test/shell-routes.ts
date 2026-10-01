// Every screen route in the canvas, by frame, for the shell tests (P15). A screen story that adds
// a route adds it here too, so the notice, the 390 px check and axe cover it.

/** The app frame's screens: Welcome, Inventory, a result, Classify, Obligations, Documents, a
 *  draft document, Ask and Your data. */
export const APP_ROUTES = [
  '/app/welcome',
  '/app/inventory',
  '/app/inventory/applicant-screening',
  '/app/classify',
  '/app/obligations',
  '/app/documents',
  '/app/documents/annex-iv',
  '/app/ask',
  '/app/your-data',
] as const

/** The site frame's pages: the landing page in both languages, the four site pages, the brand sheet. */
export const SITE_ROUTES = [
  '/',
  '/de',
  '/method',
  '/privacy',
  '/impressum',
  '/contact',
  '/brand',
] as const
