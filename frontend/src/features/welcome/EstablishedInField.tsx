import { useId, useMemo, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { countryOptions, isOutsideEu } from './countries'
import { LawQuote } from './LawQuote'

/**
 * "Where you are established": a country, with the hint naming Art. 2(1)(c) and Art. 22. Outside
 * the EU, the two provisions are quoted under it.
 */
export function EstablishedInField({
  value,
  onChange,
}: {
  value: string | null
  onChange: (code: string | null) => void
}): JSX.Element {
  const { t, i18n } = useTranslation()
  const fieldId = useId()
  const hintId = useId()
  const language = i18n.resolvedLanguage ?? 'en'
  const options = useMemo(() => countryOptions(language), [language])
  // A code from an imported file may not be in the list; keep it selectable.
  const isListed = value === null || options.some((option) => option.code === value)
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={fieldId} className="text-label font-semibold text-ink">
        {t('welcome.profile.establishedIn')}
      </label>
      <select
        id={fieldId}
        aria-describedby={hintId}
        value={value ?? ''}
        onChange={(event) => {
          onChange(event.target.value === '' ? null : event.target.value)
        }}
        className="h-11 w-full min-w-0 rounded-field border border-border-subtle bg-white px-3.5 text-body text-ink"
      >
        <option value="">{t('welcome.profile.establishedNone')}</option>
        {!isListed && <option value={value}>{value}</option>}
        {options.map((option) => (
          <option key={option.code} value={option.code}>
            {option.name}
          </option>
        ))}
      </select>
      <p id={hintId} className="m-0 text-caption text-slate">
        {t('welcome.profile.establishedHint')}
      </p>
      {isOutsideEu(value) && (
        <div className="flex flex-col gap-2">
          <LawQuote provision="art2_1_c" />
          <LawQuote provision="art22_1" />
        </div>
      )}
    </div>
  )
}
