import type { JSX } from 'react'
import { Controller, useWatch, type Control, type UseFormRegister } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { STAFF_BANDS, TURNOVER_BANDS, USED_IN } from '@/lib/company-profile'

import { ChoiceGroup } from './ChoiceGroup'
import { EstablishedInField } from './EstablishedInField'
import { COMPANY_NAME_MAX, type ProfileFormValues } from './profile-form'
import { SizeClassNote } from './SizeClassNote'

/** The fields of "About your company", in the artboard's order. */
export function ProfileFields({
  control,
  register,
}: {
  control: Control<ProfileFormValues>
  register: UseFormRegister<ProfileFormValues>
}): JSX.Element {
  const { t } = useTranslation()
  const [staffBand, turnoverBand] = useWatch({ control, name: ['staffBand', 'turnoverBand'] })
  return (
    <>
      <label className="flex flex-col gap-2">
        <span className="text-label font-semibold text-ink">
          {t('welcome.profile.companyName')}
        </span>
        <input
          type="text"
          maxLength={COMPANY_NAME_MAX}
          autoComplete="organization"
          {...register('companyName')}
          className="h-11 w-full min-w-0 rounded-field border border-border-subtle bg-white px-3.5 text-body text-ink"
        />
      </label>
      <div className="grid gap-5 md:grid-cols-2">
        <Controller
          control={control}
          name="staffBand"
          render={({ field }) => (
            <ChoiceGroup
              label={t('welcome.profile.staff')}
              options={STAFF_BANDS.map((band) => ({
                value: band,
                label: t(`welcome.staffBand.${band}`),
              }))}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
        <Controller
          control={control}
          name="turnoverBand"
          render={({ field }) => (
            <ChoiceGroup
              label={t('welcome.profile.turnover')}
              options={TURNOVER_BANDS.map((band) => ({
                value: band,
                label: t(`welcome.turnoverBand.${band}`),
              }))}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>
      <SizeClassNote staffBand={staffBand} turnoverBand={turnoverBand} />
      <div className="grid gap-5 md:grid-cols-2">
        <Controller
          control={control}
          name="establishedIn"
          render={({ field }) => (
            <EstablishedInField value={field.value} onChange={field.onChange} />
          )}
        />
        <div className="flex min-w-0 flex-col gap-2">
          <Controller
            control={control}
            name="usedIn"
            render={({ field }) => (
              <ChoiceGroup
                label={t('welcome.profile.usedIn')}
                options={USED_IN.map((where) => ({
                  value: where,
                  label: t(`welcome.usedInOption.${where}`),
                }))}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
          <p className="m-0 text-caption text-slate">{t('welcome.profile.usedInHint')}</p>
        </div>
      </div>
    </>
  )
}
