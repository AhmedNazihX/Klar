// Typed translation keys: t('pill.high_risk') is checked against the English resources.
import 'i18next'

import type en from './locales/en.json'

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: { translation: typeof en }
  }
}
