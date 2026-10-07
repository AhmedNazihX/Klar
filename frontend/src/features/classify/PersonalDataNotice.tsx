import { useDeferredValue, useMemo, type JSX } from 'react'
import { useWatch, type Control } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon'
import { findPersonalData } from '@/lib/personal-data'

import { DESCRIPTION_MAX, type DescriptionFormValues } from './description-form'

/**
 * The personal-data warning under the description field (decision 026, item 15): what the
 * in-browser check found, and to describe people by their role instead. It never blocks a run,
 * and the check sends nothing. The live region stays mounted, so a screen reader hears the
 * warning when it appears.
 */
export function PersonalDataNotice({
  control,
}: {
  control: Control<DescriptionFormValues>
}): JSX.Element {
  const { t } = useTranslation()
  const description = useDeferredValue(useWatch({ control, name: 'description' }))
  // Typing stays smooth on a long description: the check catches up between keystrokes, runs
  // once per deferred value, and reads no further than the form accepts.
  const kinds = useMemo(
    () => findPersonalData(description.slice(0, DESCRIPTION_MAX)),
    [description],
  )
  return (
    <div role="status">
      {kinds.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-card-small px-4 py-3 text-caption font-normal text-ink-2 glass-thin">
          <Icon name="alert" size={16} className="mt-0.5" />
          <div className="flex flex-col gap-1">
            <p className="m-0 font-semibold text-ink">{t('classify.personalData.title')}</p>
            <ul className="m-0 list-disc pl-5">
              {kinds.map((kind) => (
                <li key={kind}>{t(`classify.personalData.kinds.${kind}`)}</li>
              ))}
            </ul>
            <p className="m-0">{t('classify.personalData.advice')}</p>
          </div>
        </div>
      )}
    </div>
  )
}
