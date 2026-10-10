import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Citation } from '@/components/Citation'
import { useLanguage } from '@/hooks/use-language'
import { useProvision } from '@/hooks/use-provision'

import { provisionName } from './provision-names'

/** A provision quoted word for word from the corpus in the screen's language (the official
 *  German text on a German screen; the English one, labelled, where no German text exists), at
 *  the result's law version and date. Its words never come from the result (decision 031). */
export function ProvisionQuote({
  provisionId,
  result,
}: {
  provisionId: string
  result: Pick<ClassificationResult, 'law_version' | 'as_of'>
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const provision = useProvision(provisionId, language, result)
  const name = provisionName(provisionId, language)
  if (provision.isPending) {
    return (
      <p role="status" className="m-0 text-caption text-slate">
        {t('prohibited.quote.loading', { provision: name })}
      </p>
    )
  }
  if (provision.isError) {
    return (
      <p role="alert" className="m-0 text-caption text-ink-2">
        {t('prohibited.quote.failed', { provision: name })}
      </p>
    )
  }
  const { text, language: textLanguage } = provision.data
  return (
    <Citation
      language={textLanguage}
      source={t('result.citationSource', {
        provision: name,
        language: t(`result.quoteLanguage.${textLanguage}`),
      })}
    >
      {text}
    </Citation>
  )
}
