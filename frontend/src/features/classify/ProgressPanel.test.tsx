import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import { PERSON_REVIEW, providerRefused } from '@/test/classify-fixtures'
import { renderWithProviders } from '@/test/test-utils'

import { INITIAL_PROGRESS, type ProgressState } from './classify-progress'
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

/** Every check ran; the provider's content filter blocked the prohibited one (decision 030). */
function refusedProgress(): ProgressState {
  const steps = providerRefused().steps
  return {
    facts: { count: 3, questions: 1 },
    started: steps.map((step) => step.step),
    steps: Object.fromEntries(steps.map((step) => [step.step, { result: step, matches: [] }])),
    stoppedAt: null,
  }
}

async function renderRefused(language: 'en' | 'de'): Promise<HTMLElement> {
  await i18n.changeLanguage(language)
  renderWithProviders(
    <ProgressPanel
      progress={refusedProgress()}
      isRunning={false}
      failure={{ kind: 'provider_refused', steps: ['prohibited'], questions: [PERSON_REVIEW.text] }}
      onTryAgain={() => {}}
      onSaveForLater={() => {}}
    />,
  )
  return screen.findByRole('alert')
}

describe('ProgressPanel, a check the model provider refused (decision 030)', () => {
  it('names the blocked check, gives no class, asks for a person review and offers no retry', async () => {
    const alert = await renderRefused('en')
    expect(alert).toHaveTextContent('A person must review this description')
    expect(alert).toHaveTextContent(
      "The model provider's content filter blocked a check, so it couldn't be assessed automatically. No risk class is given: a person must review the description.",
    )
    expect(alert).toHaveTextContent("The model provider's content filter blocked these checks:")
    expect(within(alert).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      '2 Prohibited practices',
    ])
    expect(alert).toHaveTextContent(PERSON_REVIEW.text)
    expect(alert).toHaveTextContent(
      "Your description is kept. Klar never guesses a class for a check it couldn't assess, so there's no result.",
    )
    expect(within(alert).queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(within(alert).getByRole('button', { name: 'Save for later' })).toBeInTheDocument()
    expect(alert).not.toHaveTextContent("The checks couldn't finish")
    expect(screen.queryByText("The checks couldn't start")).toBeNull()
    expect(
      screen.getByText('Every check ran, but not every check could be assessed.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Blocked by the model provider's content filter: not assessed."),
    ).toBeInTheDocument()
  })

  it('says the same in German', async () => {
    const alert = await renderRefused('de')
    expect(alert).toHaveTextContent('Ein Mensch muss diese Beschreibung prüfen')
    expect(alert).toHaveTextContent(
      'Der Inhaltsfilter des Modellanbieters hat eine Prüfung blockiert, daher konnte sie nicht automatisch geprüft werden. Es wird keine Risikoklasse angegeben: Ein Mensch muss die Beschreibung prüfen.',
    )
    expect(alert).toHaveTextContent(
      'Der Inhaltsfilter des Modellanbieters hat diese Prüfungen blockiert:',
    )
    expect(within(alert).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      '2 Verbotene Praktiken',
    ])
    expect(alert).toHaveTextContent(
      'Ihre Beschreibung bleibt erhalten. Klar rät nie eine Einstufung für eine Prüfung, die es nicht bewerten konnte, deshalb gibt es kein Ergebnis.',
    )
    expect(within(alert).queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
    expect(within(alert).getByRole('button', { name: 'Für später speichern' })).toBeInTheDocument()
    expect(
      screen.getByText('Alle Prüfungen sind gelaufen, aber nicht jede konnte bewertet werden.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Vom Inhaltsfilter des Modellanbieters blockiert: nicht geprüft.'),
    ).toBeInTheDocument()
  })
})
