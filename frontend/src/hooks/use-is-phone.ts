import { useSyncExternalStore } from 'react'

/** Below Tailwind's `md` (48rem, 768 px): the app's phone layout (AppFrame folds the sidebar). */
const PHONE_QUERY = '(width < 48rem)'

function mediaQuery(): MediaQueryList | null {
  return typeof window.matchMedia === 'function' ? window.matchMedia(PHONE_QUERY) : null
}

function isPhoneNow(): boolean {
  return mediaQuery()?.matches ?? false
}

function subscribe(onChange: () => void): () => void {
  const query = mediaQuery()
  if (!query) return () => undefined
  query.addEventListener('change', onChange)
  return () => {
    query.removeEventListener('change', onChange)
  }
}

/**
 * True on a phone-width window, kept current as it resizes. For a control a phone shows in
 * another place (artboard `ResultMobile`): rendering it in one place only, rather than hiding a
 * second copy with CSS, keeps one control of each name on the page. Without matchMedia (jsdom) it
 * is false, the desktop layout.
 */
export function useIsPhone(): boolean {
  return useSyncExternalStore(subscribe, isPhoneNow, () => false)
}
