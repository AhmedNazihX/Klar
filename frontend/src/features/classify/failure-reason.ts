import type { TFunction } from 'i18next'

import type { ClassifyFailure } from '@/hooks/use-classify'

import { CHECK_IDS } from './classify-progress'

const HTTP_TOO_MANY = 429
const HTTP_UNAVAILABLE = 503
const HTTP_INVALID: readonly number[] = [413, 422]
const KNOWN_NODES: readonly string[] = [...CHECK_IDS, 'finalize']

/** Why the run stopped, in words: the engine's node ids and the API's statuses are mapped here;
 *  the engine's own message is only a fallback for a node the app doesn't know. */
export function failureReason(t: TFunction, failure: ClassifyFailure): string {
  switch (failure.kind) {
    case 'check':
      return KNOWN_NODES.includes(failure.node) ? t('progress.reason.check') : failure.message
    case 'network':
      return t('progress.reason.network')
    case 'incomplete':
      return t('progress.reason.incomplete')
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
