import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { classifyHandler, WORKED_EXAMPLE_EVENTS } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'

import { clearDraft } from './classification-store'

const WITH_CONTACT =
  'The tool ranks applicants. Questions go to anna.schmidt@example.com or +49 30 1234 5678.'

beforeEach(() => {
  clearDraft()
})

async function openClassify(language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  renderRoute('/app/classify')
  await screen.findByRole('heading', { level: 1 })
  return user
}

/** The live region under the description field. */
function notice(): HTMLElement {
  const field = screen.getByRole('textbox', { name: /In your own words|In Ihren eigenen Worten/ })
  const region = field.parentElement?.querySelector<HTMLElement>('[role="status"]')
  if (!region) throw new Error('No personal-data notice region under the description field.')
  return region
}

describe('the personal-data warning under the description', () => {
  it('stays empty for a description without personal data, beside the static hint', async () => {
    const user = await openClassify()
    await user.type(screen.getByLabelText('In your own words'), 'The tool ranks job applicants.')
    expect(notice()).toBeEmptyDOMElement()
    expect(
      screen.getByText('Leave out names and other personal details of applicants or staff.'),
    ).toBeInTheDocument()
  })

  it('sends nothing while it checks every kind', async () => {
    const user = await openClassify()
    const requests: string[] = []
    const record = ({ request }: { request: Request }): void => {
      requests.push(`${request.method} ${request.url}`)
    }
    server.events.on('request:start', record)
    try {
      await user.type(
        screen.getByLabelText('In your own words'),
        'Frau Schulz (schulz@example.de, 0170 1234567) is paid to DE89 3704 0044 0532 0130 00.',
      )
      await vi.waitFor(() =>
        expect(
          within(notice())
            .getAllByRole('listitem')
            .map((item) => item.textContent),
        ).toEqual([
          'an email address',
          'a phone number',
          'a bank account number (IBAN)',
          'what looks like a person’s name',
        ]),
      )
    } finally {
      server.events.removeListener('request:start', record)
    }
    expect(requests).toEqual([])
  })

  it('lists what it found and how to avoid it, in English', async () => {
    const user = await openClassify()
    await user.type(screen.getByLabelText('In your own words'), WITH_CONTACT)
    const region = notice()
    expect(
      await within(region).findByText('This description may contain personal data:'),
    ).toBeVisible()
    expect(
      within(region)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['an email address', 'a phone number'])
    expect(
      within(region).getByText(
        'Klar doesn’t need it to classify the tool. Describe people by their role instead, such ' +
          'as “the applicant” or “a team lead”. This check runs in your browser and sends nothing.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Leave out names and other personal details of applicants or staff.'),
    ).toBeInTheDocument()
  })

  it('reads the same in German, for a name and an IBAN', async () => {
    const user = await openClassify('de')
    await user.type(
      screen.getByLabelText('In Ihren eigenen Worten'),
      'Frau Müller bekommt ihr Gehalt auf DE89 3704 0044 0532 0130 00.',
    )
    const region = notice()
    expect(
      await within(region).findByText(
        'Diese Beschreibung enthält möglicherweise personenbezogene Daten:',
      ),
    ).toBeVisible()
    expect(
      within(region)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['eine Kontonummer (IBAN)', 'etwas, das wie ein Personenname aussieht'])
    expect(
      within(region).getByText(
        'Klar braucht sie für die Einstufung nicht. Beschreiben Sie Personen besser über ihre ' +
          'Rolle, etwa „die Bewerberin“ oder „eine Teamleitung“. Diese Prüfung läuft in Ihrem ' +
          'Browser und sendet nichts.',
      ),
    ).toBeInTheDocument()
  })

  it('never blocks a run: the checks start with the description as typed', async () => {
    const sent: unknown[] = []
    server.use(classifyHandler(WORKED_EXAMPLE_EVENTS, (body) => sent.push(body)))
    const user = await openClassify()
    await user.type(screen.getByLabelText('In your own words'), WITH_CONTACT)
    await within(notice()).findByText('This description may contain personal data:')
    expect(sent).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Run the checks' }))
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0]).toMatchObject({ description: WITH_CONTACT })
  })
})
