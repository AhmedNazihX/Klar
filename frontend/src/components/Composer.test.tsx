import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState, type JSX } from 'react'
import { describe, expect, it } from 'vitest'

import { Composer } from './Composer'

function Harness({ sent, isBusy = false }: { sent: string[]; isBusy?: boolean }): JSX.Element {
  const [value, setValue] = useState('')
  return (
    <Composer
      value={value}
      onChange={setValue}
      onSend={(question) => sent.push(question)}
      label="Your question"
      placeholder="Ask a question"
      sendLabel="Ask"
      isBusy={isBusy}
    />
  )
}

describe('Composer', () => {
  it('sends the trimmed question with Enter and clears the field', async () => {
    const user = userEvent.setup()
    const sent: string[] = []
    render(<Harness sent={sent} />)
    const field = screen.getByRole('textbox', { name: 'Your question' })
    await user.type(field, '  Who is a deployer?  {Enter}')
    expect(sent).toEqual(['Who is a deployer?'])
    expect(field).toHaveValue('')
  })

  it('sends with the arrow, which is quiet until there is a question', async () => {
    const user = userEvent.setup()
    const sent: string[] = []
    render(<Harness sent={sent} />)
    const arrow = screen.getByRole('button', { name: 'Ask' })
    expect(arrow).toHaveAttribute('aria-disabled', 'true')
    await user.click(arrow)
    expect(sent).toEqual([])
    await user.type(screen.getByRole('textbox'), 'Why?')
    expect(arrow).toHaveAttribute('aria-disabled', 'false')
    await user.click(arrow)
    expect(sent).toEqual(['Why?'])
  })

  it('adds a line with Shift+Enter', async () => {
    const user = userEvent.setup()
    const sent: string[] = []
    render(<Harness sent={sent} />)
    await user.type(screen.getByRole('textbox'), 'One{Shift>}{Enter}{/Shift}two')
    expect(screen.getByRole('textbox')).toHaveValue('One\ntwo')
    expect(sent).toEqual([])
  })

  it('sends nothing while an answer is on its way', async () => {
    const user = userEvent.setup()
    const sent: string[] = []
    render(<Harness sent={sent} isBusy />)
    await user.type(screen.getByRole('textbox'), 'Why?{Enter}')
    expect(sent).toEqual([])
    expect(screen.getByRole('textbox')).toHaveValue('Why?')
  })
})
