import type { CSSProperties, JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Icon } from './Icon'

export type CheckProgressState = 'done' | 'running' | 'waiting' | 'paused' | 'error'

export type CheckProgressStep = {
  /** A stable key for the row. */
  id: string
  name: ReactNode
  detail?: ReactNode
  state: CheckProgressState
  /** The closest matches a step compared, e.g. "Annex III 4(a): recruitment". */
  matches?: readonly { id: string; label: ReactNode }[]
}

function Marker({ state }: { state: CheckProgressState }): JSX.Element {
  const base = 'flex size-6 shrink-0 items-center justify-center rounded-full'
  switch (state) {
    case 'done':
      return (
        <span className={cn(base, 'bg-risk-minimal-tint text-risk-minimal')}>
          <Icon name="check" size={13} />
        </span>
      )
    case 'error':
      return (
        <span className={cn(base, 'bg-risk-prohibited-tint text-risk-prohibited')}>
          <Icon name="alert" size={14} />
        </span>
      )
    case 'running':
      return <span aria-hidden="true" className={cn(base, 'check-ring')} />
    case 'paused':
      return (
        <span aria-hidden="true" className={cn(base, 'check-pause')}>
          <span className="size-2 rounded-full bg-lens-blue" />
        </span>
      )
    case 'waiting':
      return (
        <span
          aria-hidden="true"
          className={cn(base, 'shadow-[inset_0_0_0_1.5px_rgb(15_27_45/0.35)]')}
        />
      )
  }
}

/**
 * The live list of checks while Klar classifies a tool, always in the Act's order. Changes are
 * announced politely; every state is also in words (a hidden state word, and the detail line),
 * so the motion is never the only signal. The running step is lifted in white glass with a Lens
 * blue ring; a paused step pulses in Lens blue; a check that couldn't finish is plain red.
 */
export function CheckProgress({
  steps,
  className,
}: {
  steps: readonly CheckProgressStep[]
  className?: string
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <ol
      aria-live="polite"
      className={cn('check-list m-0 flex list-none flex-col gap-1 p-0', className)}
    >
      {steps.map((step, index) => (
        <li
          key={step.id}
          data-state={step.state}
          style={{ '--check-step': index } as CSSProperties}
          className={cn(
            'flex items-start gap-3 rounded-item px-3 py-2.5',
            step.state === 'running' &&
              'bg-white/78 shadow-[inset_0_1px_0_#fff,0_0_0_1.5px_rgb(45_75_224/0.35),0_10px_24px_-12px_rgb(45_75_224/0.45)]',
            step.state === 'waiting' && 'opacity-60',
          )}
        >
          <Marker state={step.state} />
          <span className="flex min-w-0 grow flex-col gap-0.5">
            <span className="text-body-small font-semibold text-ink">
              {step.name}
              <span className="sr-only">: {t(`progress.state.${step.state}`)}</span>
            </span>
            {step.detail && (
              <span
                className={cn(
                  'text-caption font-normal',
                  step.state === 'error' ? 'text-risk-prohibited' : 'text-slate',
                )}
              >
                {step.detail}
              </span>
            )}
            {step.matches && step.matches.length > 0 && (
              <span className="mt-1.5 flex flex-col gap-1.5">
                {step.matches.map((match) => (
                  <span
                    key={match.id}
                    className="rounded-[10px] px-2.5 py-1.5 text-caption font-normal text-ink glass-thin"
                  >
                    {match.label}
                  </span>
                ))}
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}
