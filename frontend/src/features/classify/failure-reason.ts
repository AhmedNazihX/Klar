import type { TFunction } from 'i18next'

import type { ClassifyFailure } from '@/hooks/use-classify'

const HTTP_TOO_MANY = 429
const HTTP_UNAVAILABLE = 503
const HTTP_INVALID: readonly number[] = [413, 422]

/** Why the run stopped, in words. A check that couldn't finish gets one fixed sentence, whatever
 *  the node: the row it stopped at says which check, and the engine's own message is never shown
 *  (it is not written for users). The API's statuses are mapped here. */
export function failureReason(t: TFunction, failure: ClassifyFailure): string {
  switch (failure.kind) {
    case 'check':
      return t('progress.reason.check')
    case 'network':
      return t('progress.reason.network')
    case 'incomplete':
      return t('progress.reason.incomplete')
    case 'needs_description':
      return t('progress.reason.needsDescription')
    case 'provider_refused':
      return t('progress.reason.providerRefused')
    case 'http': {
      const seconds = failure.retryAfterSeconds
      if (failure.status === HTTP_TOO_MANY) {
        return seconds === null
          ? t('progress.reason.tooManyNoTime')
          : t('progress.reason.tooMany', { seconds })
      }
      if (failure.status === HTTP_UNAVAILABLE) {
        return seconds === null
          ? t('progress.reason.unavailable')
          : t('progress.reason.busy', { seconds })
      }
      if (HTTP_INVALID.includes(failure.status)) return t('progress.reason.invalid')
      return t('progress.reason.server', { status: failure.status })
    }
  }
}
