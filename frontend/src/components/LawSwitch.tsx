import { useEffect, useRef, useState, type JSX, type ReactNode, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'

import { SegmentedControl } from './SegmentedControl'

export type LawVersion = 'amended' | 'original'

/** The class LawSwitch puts on its scope while the original 2024 text is shown (index.css › law-version). */
export const LAW_ORIGINAL_CLASS = 'law-original'
/** Wrap a screen in this class to keep the switch's effect inside it; otherwise it is the document. */
export const LAW_SCOPE_CLASS = 'law-scope'

export type LawSwitchProps = {
  /** Element whose class law-original is toggled; defaults to the closest .law-scope, then the document. */
  scope?: RefObject<HTMLElement | null>
  value?: LawVersion
  defaultValue?: LawVersion
  onChange?: (value: LawVersion) => void
  label?: string
  /** The options' labels; a node, so a screen can show a compact label on a phone. */
  amendedLabel?: ReactNode
  originalLabel?: ReactNode
  className?: string
}

/**
 * The law version switch: As amended (the default, the text Klar classifies under) or the original
 * 2024 text. It is visual only: picking the original swaps every LawDate and shows the LawNotice in
 * its scope. Keep the choice in the route's search params by passing `value` and `onChange`.
 */
export function LawSwitch({
  scope,
  value,
  defaultValue = 'amended',
  onChange,
  label,
  amendedLabel,
  originalLabel,
  className,
}: LawSwitchProps): JSX.Element {
  const { t } = useTranslation()
  const [ownValue, setOwnValue] = useState<LawVersion>(defaultValue)
  const current = value ?? ownValue
  const anchorRef = useRef<HTMLSpanElement>(null)

  // The scope is a DOM element outside this component: keep its class in step with the choice.
  useEffect(() => {
    const target =
      scope?.current ??
      anchorRef.current?.closest<HTMLElement>(`.${LAW_SCOPE_CLASS}`) ??
      document.documentElement
    target.classList.toggle(LAW_ORIGINAL_CLASS, current === 'original')
    return () => {
      target.classList.remove(LAW_ORIGINAL_CLASS)
    }
  }, [current, scope])

  return (
    <span ref={anchorRef} className="inline-flex">
      <SegmentedControl<LawVersion>
        label={label ?? t('law.label')}
        value={current}
        onChange={(next) => {
          if (value === undefined) setOwnValue(next)
          onChange?.(next)
        }}
        options={[
          { value: 'amended', label: amendedLabel ?? t('law.amended') },
          { value: 'original', label: originalLabel ?? t('law.original') },
        ]}
        className={className}
      />
    </span>
  )
}
