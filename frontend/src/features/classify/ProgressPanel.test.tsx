import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { INITIAL_PROGRESS } from './classify-progress'
import { ProgressPanel } from './ProgressPanel'

const QUESTIONS = ['First question?', 'Second question?', 'Third question?']

async function renderThin(language: 'en' | 'de'): Promise<HTMLElement> {
  await i18n.changeLanguage(language)
  renderWithProviders(
    <ProgressPanel
      progress={INITIAL_PROGRESS}
      isRunning={false}
      failure={{ kind: 'needs_description', questions: QUESTIONS }}
      onTryAgain={() => {}}
      onSaveForLater={() => {}}
    />,
  )
  return screen.findByRole('alert')
}

afterEach(async () => {
  await i18n.changeLanguage('en')
})

describe('ProgressPanel, a description too thin to start (E13)', () => {
  it('asks what the tool decides and whom it affects, and lists the three questions', async () => {
    const alert = await renderThin('en')
    expect(alert).toHaveTextContent('Klar needs a little more to start')
    expect(alert).toHaveTextContent(
      'Klar needs to know what the tool decides and who it affects. Add that to your description and run it again.',
    )
    const items = within(alert).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual(QUESTIONS)
    expect(alert).not.toHaveTextContent("The checks couldn't finish")
    expect(alert).not.toHaveTextContent('when a check fails')
    expect(
      screen.getByText('Waiting for a description. Nothing is guessed in the meantime.'),
    ).toBeInTheDocument()
  })

  it('says the same in German', async () => {
    const alert = await renderThin('de')
    expect(alert).toHaveTextContent('Klar braucht etwas mehr, um zu starten')
    expect(alert).toHaveTextContent(
      'Klar muss wissen, was das Tool entscheidet und wen es betrifft. Ergänzen Sie das in Ihrer Beschreibung und starten Sie die Prüfungen erneut.',
    )
    expect(within(alert).getAllByRole('listitem')).toHaveLength(QUESTIONS.length)
    expect(alert).not.toHaveTextContent('Die Prüfungen konnten nicht abgeschlossen werden')
    expect(
      screen.getByText('Wartet auf eine Beschreibung. Bis dahin wird nichts geraten.'),
    ).toBeInTheDocument()
  })
})
