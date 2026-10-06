import { z } from 'zod'

import {
  STAFF_BANDS,
  TURNOVER_BANDS,
  USED_IN,
  type CompanyProfile,
  type CompanyProfileInput,
} from '@/lib/company-profile'

const COMPANY_NAME_MAX = 200

/** The profile form's fields. Every one is optional ("Skip for now" saves nothing at all). */
export const ProfileFormSchema = z.object({
  companyName: z.string().trim().max(COMPANY_NAME_MAX),
  staffBand: z.enum(STAFF_BANDS).nullable(),
  turnoverBand: z.enum(TURNOVER_BANDS).nullable(),
  establishedIn: z
    .string()
    .regex(/^[A-Z]{2}$/)
    .nullable(),
  usedIn: z.enum(USED_IN).nullable(),
})
export type ProfileFormValues = z.infer<typeof ProfileFormSchema>

/** The form's starting values: the saved profile, or nothing chosen. */
export function toFormValues(profile: CompanyProfile | null | undefined): ProfileFormValues {
  return {
    companyName: profile?.companyName ?? '',
    staffBand: profile?.staffBand ?? null,
    turnoverBand: profile?.turnoverBand ?? null,
    establishedIn: profile?.establishedIn ?? null,
    usedIn: profile?.usedIn ?? null,
  }
}

/** What gets written: a blank name is no name. */
export function toProfileInput(values: ProfileFormValues): CompanyProfileInput {
  const companyName = values.companyName.trim()
  return {
    companyName: companyName === '' ? null : companyName,
    staffBand: values.staffBand,
    turnoverBand: values.turnoverBand,
    establishedIn: values.establishedIn,
    usedIn: values.usedIn,
  }
}

export { COMPANY_NAME_MAX }
