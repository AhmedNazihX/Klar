import { useState, type JSX, type KeyboardEvent } from 'react'

import { cn } from '@/lib/utils'

import { Icon } from './Icon'

export type ComposerProps = {
  /** The question being written (the field is controlled: "Try asking" fills it). */
  value: string
  onChange: (value: string) => void
  /** Called with the trimmed question; the field is then cleared through `onChange`. */
  onSend: (question: string) => void
  /** The field's accessible name, e.g. "Your question". */
  label: string
  placeholder: string
  /** The arrow's accessible name, e.g. "Ask". */
  sendLabel: string
  /** While an answer is on its way, nothing more is sent. */
  isBusy?: boolean
  maxLength?: number
  id?: string
  className?: string
}

/**
 * The question field (components.md › Composer): one white glass field with the send arrow in its
 * corner. Enter asks, Shift+Enter adds a line. The arrow is quiet (slate on faint grey) until there
 * is a question, then the Lens blue liquid button; it lifts on hover and flies up as the question
 * goes, and the field clears. Reduced motion keeps it still (index.css › composer).
 */
export function Composer({
  value,
  onChange,
  onSend,
  label,
  placeholder,
  sendLabel,
  isBusy = false,
  maxLength,
  id,
  className,
}: ComposerProps): JSX.Element {
  const [isSent, setIsSent] = useState(false)
  const question = value.trim()
  const canSend = question.length > 0 && !isBusy

  function send(): void {
    if (!canSend) return
    onSend(question)
    onChange('')
    setIsSent(true)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    send()
  }

  return (
    <div
      className={cn(
        'flex items-end gap-2 rounded-[22px] bg-white/80 py-1.5 pr-1.5 pl-4 shadow-[inset_0_0_0_1px_var(--color-hairline)] focus-within:shadow-[inset_0_0_0_1px_var(--color-lens-blue),0_0_0_4px_rgb(45_75_224/0.14)]',
        className,
      )}
    >
      <textarea
        id={id}
        aria-label={label}
        rows={1}
        value={value}
        maxLength={maxLength}
        placeholder={placeholder}
        onChange={(event) => {
          onChange(event.target.value)
        }}
        onKeyDown={onKeyDown}
        className="[field-sizing:content] max-h-40 min-h-11 min-w-0 md:min-h-[40px] flex-1 resize-none border-0 bg-transparent py-2 text-body-small text-ink outline-none placeholder:text-slate"
      />
      <button
        type="button"
        aria-label={sendLabel}
        aria-disabled={!canSend}
        onClick={send}
        onAnimationEnd={() => {
          setIsSent(false)
        }}
        className={cn(
          'relative inline-flex size-11 shrink-0 md:size-10 cursor-pointer items-center justify-center overflow-hidden rounded-full border-0 transition-[translate,box-shadow] duration-(--duration-press) ease-settle',
          canSend
            ? 'liquid-primary text-white shadow-button motion-safe:hover:-translate-y-0.5'
            : 'cursor-default bg-ink/6 text-slate',
          isSent && 'composer-sent',
        )}
      >
        <Icon name="send" size={18} />
      </button>
    </div>
  )
}
