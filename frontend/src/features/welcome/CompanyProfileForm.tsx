import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { useId, useMemo, type JSX } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { useSaveCompanyProfile } from '@/hooks/use-save-company-profile'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'
import { supabase } from '@/lib/supabase'

import { ProfileFields } from './ProfileFields'
import {
  ProfileFormSchema,
  toFormValues,
  toProfileInput,
  type ProfileFormValues,
} from './profile-form'
import { WriteFailureMessage } from './WriteFailureMessage'

/**
 * "About your company": Save writes the profile onto the inventory and goes on to Classify; Skip
 * goes there without writing anything. The profile is not an input to classification.
 */
export function CompanyProfileForm(): JSX.Element {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const headingId = useId()
  const overview = useUserDataOverview()
  const save = useSaveCompanyProfile()
  const savedProfile = overview.data?.profile
  // The saved profile fills the form once it arrives; fields the user already changed are kept.
  const values = useMemo(() => toFormValues(savedProfile), [savedProfile])
  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(ProfileFormSchema),
    defaultValues: values,
    values,
    resetOptions: { keepDirtyValues: true },
  })
  // Without the overview, Save can't tell whether an inventory exists, and could add a second one.
  // Without Supabase nothing can be saved at all.
  const canSave = supabase !== null && !overview.isLoading && !overview.isError && !save.isPending

  const submit = form.handleSubmit((submitted) => {
    save.mutate(
      {
        inventoryId: overview.data?.inventoryId ?? null,
        profile: toProfileInput(submitted),
        inventoryName: t('welcome.inventoryName'),
      },
      { onSuccess: () => void navigate({ to: '/app/classify' }) },
    )
  })

  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-1 flex-col gap-5"
    >
      <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id={headingId} className="m-0 text-heading-panel text-ink">
            {t('welcome.profile.heading')}
          </h2>
          <p className="m-0 text-caption text-slate">{t('welcome.profile.subtitle')}</p>
        </div>
        <ProfileFields control={form.control} register={form.register} />
        {save.isError && <WriteFailureMessage error={save.error} kind="save" />}
        {overview.isError && <WriteFailureMessage error={overview.error} kind="save" />}
        <div className="flex flex-wrap justify-end gap-2.5">
          <Button variant="ghost" onClick={() => void navigate({ to: '/app/classify' })}>
            {t('welcome.profile.skip')}
          </Button>
          <Button type="submit" disabled={!canSave}>
            {save.isPending ? t('welcome.profile.saving') : t('welcome.profile.save')}
          </Button>
        </div>
      </form>
    </GlassPanel>
  )
}
