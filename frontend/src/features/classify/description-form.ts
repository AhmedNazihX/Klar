import { z } from 'zod'

/** The API's limit on a description (ClassifyRequest, backend). */
export const DESCRIPTION_MAX = 20_000
/** The systems table's limit on a tool's name. */
const NAME_MAX = 200

/** The description form: an optional name and the description the checks run on. */
export const DescriptionFormSchema = z.object({
  name: z.string().trim().max(NAME_MAX, { error: 'classify.nameTooLong' }),
  description: z
    .string()
    .trim()
    .min(1, { error: 'classify.descriptionRequired' })
    .max(DESCRIPTION_MAX, { error: 'classify.descriptionTooLong' }),
})
export type DescriptionFormValues = z.infer<typeof DescriptionFormSchema>

/** The i18n key a field's error carries, if it is one of ours. */
export function errorKey(
  message: string | undefined,
): 'classify.nameTooLong' | 'classify.descriptionRequired' | 'classify.descriptionTooLong' | null {
  switch (message) {
    case 'classify.nameTooLong':
    case 'classify.descriptionRequired':
    case 'classify.descriptionTooLong':
      return message
    default:
      return null
  }
}
