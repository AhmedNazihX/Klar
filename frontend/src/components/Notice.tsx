import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

export type NoticeProps = {
  /** Extends the line where it helps; it must keep both halves (guidance, and the AI notice). */
  children?: ReactNode
  className?: string
}

/** The line every screen and exported document carries, in micro type at the foot of the column. */
export function Notice({ children, className }: NoticeProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <p className={cn('m-0 text-micro text-slate', className)}>{children ?? t('notice.default')}</p>
  )
}
