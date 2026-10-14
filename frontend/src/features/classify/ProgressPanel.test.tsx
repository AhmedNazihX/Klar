import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import { needsDescription, PERSON_REVIEW, providerRefused } from '@/test/classify-fixtures'
import { renderWithProviders } from '@/test/test-utils'

import { INITIAL_PROGRESS, type ProgressState } from './classify-progress'
import { ProgressPanel } from './ProgressPanel'

const QUESTIONS = needsDescription().follow_up_questions ?? []

async function renderThin(language: 'en' | 'de', isRerun = false): Promise<void> {
  await i18n.changeLanguage(language)
  renderWithProviders(
    <ProgressPanel
      progress={INITIAL_PROGRESS}
      isRunning={false}
      failure={{ kind: 'needs_description', questions: QUESTIONS }}
      onTryAgain={() => {}}
      onSaveForLater={() => {}}
      isRerun={isRerun}
    />,
  )
}

afterEach(async () => {
  await i18n.changeLanguage('en')
})

describe('ProgressPanel, a description too thin to start (E13, artboard ClassifyVague)', () => {
  it('waits for a description in place of the check list, with no alert and no Try again', async () => {
    await renderThin('en')
    const panel = await screen.findByRole('region', { name: "Checking in the Act's order" })
    expect(within(panel).getByText('Waiting for a description')).toBeVisible()
    expect(
      within(panel).getByText(
        'The four checks start once Klar has enough to go on. Nothing is guessed in the meantime.',
      ),
    ).toBeVisible()
    expect(
      within(panel).getByText('No step is skipped. This usually takes under a minute.'),
    ).toBeVisible()
    expect(within(panel).queryByRole('list')).toBeNull()
    expect(within(panel).queryByRole('alert')).toBeNull()
    expect(within(panel).queryByRole('button')).toBeNull()
  })

  it('says the same in German', async () => {
    await renderThin('de')
    const panel = await screen.findByRole('region', {
      name: 'Prüfung in der Reihenfolge der Verordnung',
    })
    expect(within(panel).getByText('Wartet auf eine Beschreibung')).toBeVisible()
    expect(
      within(panel).getByText(
        'Die vier Prüfungen beginnen, sobald Klar genug Angaben hat. Bis dahin wird nichts geraten.',
      ),
    ).toBeVisible()
    expect(within(panel).queryByRole('list')).toBeNull()
  })

  it("on a result's re-run, says the earlier result stands and lists the three prompts", async () => {
    await renderThin('en', true)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your earlier result still stands')
    expect(alert).toHaveTextContent(
      'Klar needs to know what the tool decides and who it affects. Add that to your description and run it again.',
    )
    const items = within(alert).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      'What does it decide or suggest?',
      'Who does it affect?',
      'Did you buy it or build it?',
    ])
    expect(screen.queryByText('Waiting for a description')).toBeNull()
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

async function renderRefused(language: 'en' | 'de', isRerun = false): Promise<HTMLElement> {
  await i18n.changeLanguage(language)
  renderWithProviders(
    <ProgressPanel
      progress={refusedProgress()}
      isRunning={false}
      failure={{ kind: 'provider_refused', steps: ['prohibited'], questions: [PERSON_REVIEW.text] }}
      onTryAgain={() => {}}
      // A result's re-run has nothing waiting to be saved (ResultScreen passes none).
      onSaveForLater={isRerun ? undefined : () => {}}
      isRerun={isRerun}
    />,
  )
  return screen.findByRole('alert')
}

describe("ProgressPanel, a result's re-run the model provider refused", () => {
  it.each([
    [
      'en',
      'Your earlier result still stands',
      "The model provider's content filter blocked a check in the new run, so it couldn't be assessed automatically: a person must review the description and your answers.",
      "Your answers are kept. Klar never guesses a class for a check it couldn't assess, so the new run gives no result.",
      "Blocked by the model provider's content filter: not assessed.",
    ],
    [
      'de',
      'Ihr bisheriges Ergebnis gilt weiter',
      'Der Inhaltsfilter des Modellanbieters hat im neuen Durchlauf eine Prüfung blockiert, daher konnte sie nicht automatisch geprüft werden: Ein Mensch muss die Beschreibung und Ihre Antworten prüfen.',
      'Ihre Antworten bleiben erhalten. Klar rät nie eine Einstufung für eine Prüfung, die es nicht bewerten konnte, deshalb ergibt der neue Durchlauf kein Ergebnis.',
      'Vom Inhaltsfilter des Modellanbieters blockiert: nicht geprüft.',
    ],
  ] as const)(
    'says the earlier result stands, and leaves the blocked checks to their rows (%s)',
    async (language, title, reason, body, row) => {
      const alert = await renderRefused(language, true)
      expect(alert).toHaveTextContent(title)
      expect(alert).toHaveTextContent(reason)
      // The earlier result still shows: the alert never says no class is given.
      expect(alert).not.toHaveTextContent(/No risk class is given|keine Risikoklasse/)
      expect(alert).toHaveTextContent(body)
      expect(alert).toHaveTextContent(PERSON_REVIEW.text)
      expect(alert).not.toHaveTextContent(/so there's no result|deshalb gibt es kein Ergebnis/)
      expect(within(alert).queryByRole('list')).toBeNull()
      expect(within(alert).queryByRole('button')).toBeNull()
      expect(screen.getByText(row)).toBeInTheDocument()
    },
  )
})

describe('ProgressPanel, a check the model provider refused (decision 030)', () => {
  it('names the blocked check, gives no class, asks for a person review and offers no retry', async () => {
    const alert = await renderRefused('en')
    expect(alert).toHaveTextContent('A person must review this description')
    expect(alert).toHaveTextContent(
      "The model provider's content filter blocked a check, so it couldn't be assessed automatically. No risk class is given: a person must review the description.",
    )
    expect(alert).toHaveTextContent("The model provider's content filter blocked these checks:")
    expect(
      within(alert)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['2 Prohibited practices'])
    expect(alert).toHaveTextContent(PERSON_REVIEW.text)
    expect(alert).toHaveTextContent(
      "Your description is kept. Klar never guesses a class for a check it couldn't assess, so there's no result.",
    )
    expect(within(alert).queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(within(alert).getByRole('button', { name: 'Save for later' })).toBeInTheDocument()
    expect(alert).not.toHaveTextContent("The checks couldn't finish")
    expect(screen.queryByText("The checks couldn't start")).toBeNull()
    expect(screen.getByText('Not every check could be assessed.')).toBeInTheDocument()
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
    expect(
      within(alert)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['2 Verbotene Praktiken'])
    expect(alert).toHaveTextContent(
      'Ihre Beschreibung bleibt erhalten. Klar rät nie eine Einstufung für eine Prüfung, die es nicht bewerten konnte, deshalb gibt es kein Ergebnis.',
    )
    expect(within(alert).queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
    expect(within(alert).getByRole('button', { name: 'Für später speichern' })).toBeInTheDocument()
    expect(screen.getByText('Nicht jede Prüfung konnte bewertet werden.')).toBeInTheDocument()
    expect(
      screen.getByText('Vom Inhaltsfilter des Modellanbieters blockiert: nicht geprüft.'),
    ).toBeInTheDocument()
  })
})

describe('ProgressPanel, a refused check followed by a stopping check that ended the run', () => {
  /** Scope refused, then a decided Art. 5 match ended the run: the later checks never ran. */
  function endedEarly(): ProgressState {
    const [scope, prohibited] = providerRefused().steps
    if (!scope || !prohibited) throw new Error('The fixture lists every check.')
    const steps = [
      { ...scope, status: 'needs_more_information' as const, error: 'provider_refusal' },
      { ...prohibited, status: 'decided' as const },
    ]
    return {
      facts: { count: 3, questions: 1 },
      started: steps.map((step) => step.step),
      steps: Object.fromEntries(steps.map((step) => [step.step, { result: step, matches: [] }])),
      stoppedAt: null,
    }
  }

  it.each([
    ['en', 'Not every check could be assessed.', 'Every check ran'],
    ['de', 'Nicht jede Prüfung konnte bewertet werden.', 'Alle Prüfungen sind gelaufen'],
  ] as const)('never says every check ran (%s)', async (language, subtitle, claim) => {
    await i18n.changeLanguage(language)
    renderWithProviders(
      <ProgressPanel
        progress={endedEarly()}
        isRunning={false}
        failure={{ kind: 'provider_refused', steps: ['scope'], questions: [PERSON_REVIEW.text] }}
        onTryAgain={() => {}}
        onSaveForLater={() => {}}
      />,
    )
    await screen.findByRole('alert')
    expect(screen.getByText(subtitle)).toBeInTheDocument()
    expect(screen.queryByText(new RegExp(claim))).toBeNull()
  })
})
