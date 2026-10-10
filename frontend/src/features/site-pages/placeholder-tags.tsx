import { Placeholder } from '@/components/Placeholder'

/** Marks every `<ph>…</ph>` in a translated line as a placeholder (Trans `components`). */
export const PLACEHOLDER_TAGS = { ph: <Placeholder /> } as const
