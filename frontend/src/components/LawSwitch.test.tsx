import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { useRef, type JSX } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { LawDate } from './LawDate'
import { LawNotice } from './LawNotice'
import { LAW_ORIGINAL_CLASS, LAW_SCOPE_CLASS, LawSwitch } from './LawSwitch'

// Vitest does not load CSS, so the law-version rules from index.css are put on the page by hand:
// the swap below is the real stylesheet's, not a copy.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')
const LAW_RULES =
  /\/\* law-version:start[\s\S]*?\*\/([\s\S]*?)\/\* law-version:end \*\//.exec(css)?.[1] ?? ''

let style: HTMLStyleElement
beforeEach(() => {
  style = document.createElement('style')
  style.textContent = LAW_RULES
  document.head.append(style)
})
afterEach(() => {
  style.remove()
})

function Screen(): JSX.Element {
  return (
    <div className={LAW_SCOPE_CLASS} data-testid="scope">
      <LawSwitch />
      <p>
        Duties apply from <LawDate amended="2 December 2027" original="2 August 2026" />.
      </p>
      <LawNotice />
    </div>
  )
}

describe('LawSwitch, LawDate and LawNotice', () => {
  it('has the rules to load', () => {
    expect(LAW_RULES).toContain('.law-original .law-original-only')
  })

  it('shows the amended text by default, with the switch pressed on it', async () => {
    renderWithProviders(<Screen />)
    expect(await screen.findByRole('button', { name: 'As amended, 27 Jul 2026' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Original, 2024' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByText('2 December 2027')).toBeVisible()
    expect(screen.getByText('2 August 2026')).not.toBeVisible()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('swaps every moved date and shows the notice under the original scope', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(
      <div className={LAW_SCOPE_CLASS} data-testid="scope">
        <LawSwitch onChange={onChange} />
        <LawDate amended="2 December 2027" original="2 August 2026" />
        <LawNotice />
      </div>,
    )

    await user.click(await screen.findByRole('button', { name: 'Original, 2024' }))

    expect(onChange).toHaveBeenCalledExactlyOnceWith('original')
    expect(screen.getByRole('button', { name: 'Original, 2024' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByTestId('scope')).toHaveClass(LAW_ORIGINAL_CLASS)
    expect(document.documentElement).not.toHaveClass(LAW_ORIGINAL_CLASS)
    expect(screen.getByText('2 August 2026')).toBeVisible()
    expect(screen.getByText('2 December 2027')).not.toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent(/original 2024 text/)

    await user.click(screen.getByRole('button', { name: 'As amended, 27 Jul 2026' }))
    expect(screen.getByTestId('scope')).not.toHaveClass(LAW_ORIGINAL_CLASS)
    expect(screen.getByText('2 December 2027')).toBeVisible()
  })

  it('uses the scope it is given, and the document when there is none', async () => {
    const user = userEvent.setup()
    function WithRef(): JSX.Element {
      const scope = useRef<HTMLDivElement>(null)
      return (
        <>
          <LawSwitch scope={scope} />
          <div ref={scope} data-testid="given" />
        </>
      )
    }
    const { unmount } = renderWithProviders(<WithRef />)
    await user.click(await screen.findByRole('button', { name: 'Original, 2024' }))
    expect(screen.getByTestId('given')).toHaveClass(LAW_ORIGINAL_CLASS)
    unmount()

    renderWithProviders(<LawSwitch defaultValue="original" />)
    await screen.findByRole('button', { name: 'Original, 2024' })
    expect(document.documentElement).toHaveClass(LAW_ORIGINAL_CLASS)
  })

  it('takes its labels from the active language', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(<LawSwitch />)
    expect(await screen.findByRole('group', { name: 'Gesetzesfassung' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ursprüngliche Fassung, 2024' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})
