import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Icon } from './Icon'

export type LawNoticeProps = {
  /** What the reader is viewing and what moved; defaults to the translated line. */
  children?: ReactNode
  className?: string
}

/** The line under the top bar while the original 2024 text is shown. Hidden in the default view. */
export function LawNotice({ children, className }: LawNoticeProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      className={cn(
        'law-notice items-center gap-2.5 rounded-card-small px-4 py-3 text-sm leading-normal text-ink-2 glass-thin',
        className,
      )}
    >
      <Icon name="info" size={16} />
      <span>{children ?? t('law.notice')}</span>
    </div>
  )
}
