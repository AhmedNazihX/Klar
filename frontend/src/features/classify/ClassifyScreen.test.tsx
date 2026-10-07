import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { delay, http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassifyResponse } from '@/api'
import {
  CLASSIFY_URL,
  classifyHandler,
  sseBody,
  WORKED_EXAMPLE_DESCRIPTION,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'

import { clearDraft } from './classification-store'

beforeEach(() => {
  clearDraft()
})

async function openClassify(language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute('/app/classify')
  await screen.findByRole('heading', { level: 1 })
  return { user, ...rendered }
}

async function describeAndRun(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('What do you call the tool?'), 'Applicant screening')
  await user.type(screen.getByLabelText('In your own words'), WORKED_EXAMPLE_DESCRIPTION)
  await user.click(screen.getByRole('button', { name: 'Run the checks' }))
}

function checkList(): HTMLElement {
  const panel = screen.getByRole('region', { name: "Checking in the Act's order" })
  return within(panel).getByRole('list')
}

/** The recorded events up to and including the high-risk step, then an error at transparency. */
function eventsStoppingAtTransparency(): ClassifyResponse[] {
  const upTo = WORKED_EXAMPLE_EVENTS.findIndex(
    (event) => event.event === 'step_started' && event.step === 'transparency',
  )
  return [
    ...WORKED_EXAMPLE_EVENTS.slice(0, upTo + 1),
    { event: 'error', step: 'transparency', message: 'The check could not finish.' },
  ]
}

describe('Classify, the description form', () => {
  it('asks for a description before running anything', async () => {
    let requests = 0
    server.use(
      http.post(CLASSIFY_URL, () => {
        requests += 1
        return HttpResponse.json({}, { status: 500 })
      }),
    )
    const { user } = await openClassify()
    await user.click(screen.getByRole('button', { name: 'Run the checks' }))
    expect(await screen.findByText('Describe the tool in a sentence or two first.')).toBeVisible()
    expect(screen.getByLabelText('In your own words')).toHaveAttribute('aria-invalid', 'true')
    expect(requests).toBe(0)
  })

  it('shows the four things worth mentioning, the privacy line and every check waiting', async () => {
    await openClassify()
    expect(screen.getByText('who it affects')).toBeInTheDocument()
    expect(
      screen.getByText('Leave out names and other personal details of applicants or staff.'),
    ).toBeInTheDocument()
    const rows = within(checkList()).getAllByRole('listitem')
    expect(rows.map((row) => row.dataset.state)).toEqual(Array(6).fill('waiting'))
    expect(checkList()).toHaveAttribute('aria-live', 'polite')
  })

  it('passes axe', async () => {
    const { container } = await openClassify()
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe('Classify, a run', () => {
  it('sends the description in the screen language and opens the result', async () => {
    let body: unknown = null
    server.use(
      classifyHandler(WORKED_EXAMPLE_EVENTS, (sent) => {
        body = sent
      }),
    )
    const { user, router } = await openClassify()
    await describeAndRun(user)

    await expect.poll(() => router.state.location.pathname).toMatch(/^\/app\/inventory\/[\w-]+$/)
    expect(body).toEqual({ description: WORKED_EXAMPLE_DESCRIPTION, language: 'en' })
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Applicant screening' }),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('region', { name: 'Result' })).getByText('High-risk'),
    ).toBeVisible()
  })

  it('shows each check as the stream reports it, and the Annex points it matched', async () => {
    // The result arrives late, so the list can be read in between.
    const events = WORKED_EXAMPLE_EVENTS.slice(0, -1)
    const encoder = new TextEncoder()
    server.use(
      http.post(CLASSIFY_URL, () => {
        const stream = new ReadableStream({
          async start(controller) {
            controller.enqueue(encoder.encode(sseBody(events)))
            await delay('infinite')
          },
        })
        return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
      }),
    )
    const { user } = await openClassify()
    await describeAndRun(user)

    const highRisk = await within(checkList()).findByText(
      'Annex III 4(a): recruitment and selection of people',
    )
    expect(highRisk).toBeVisible()
    const rows = within(checkList()).getAllByRole('listitem')
    expect(rows.map((row) => row.dataset.state)).toEqual([
      'done',
      'paused',
      'done',
      'done',
      'done',
      'done',
    ])
    expect(rows[0]).toHaveTextContent('4 facts found, 5 to confirm')
    expect(rows[2]).toHaveTextContent('No match. Art. 5')
    expect(screen.getByRole('button', { name: 'Checking…' })).toBeDisabled()
  })

  it('stops at the check that failed, keeps the description and shows no class', async () => {
    let requests = 0
    server.use(
      http.post(CLASSIFY_URL, () => {
        requests += 1
        return new HttpResponse(sseBody(eventsStoppingAtTransparency()), {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )
    const { user, router } = await openClassify()
    await describeAndRun(user)

    expect(await screen.findByRole('alert')).toHaveTextContent("The checks couldn't finish")
    expect(screen.getByText('Stopped at check 4 of 4.')).toBeVisible()
    const rows = within(checkList()).getAllByRole('listitem')
    expect(rows[4]).toHaveAttribute('data-state', 'error')
    expect(rows[4]).toHaveTextContent("Stopped: this check couldn't finish.")
    expect(rows[5]).toHaveTextContent('Not run yet')
    expect(screen.queryByRole('region', { name: 'Result' })).toBeNull()
    expect(screen.getByLabelText('In your own words')).toHaveValue(WORKED_EXAMPLE_DESCRIPTION)
    expect(router.state.location.pathname).toBe('/app/classify')
    // Never sent again on its own: each run is paid.
    expect(requests).toBe(1)

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await expect.poll(() => requests).toBe(2)
  })

  it.each([
    [429, '7', "You've started many checks in a short time. Try again in 7 seconds."],
    [503, '10', 'Klar is busy right now. Try again in 10 seconds.'],
    [503, null, "The checks aren't available right now. Try again later."],
    [422, null, "The description couldn't be sent. Keep it under 20,000 characters and try again."],
  ] as const)('says why the API refused a run (%i)', async (status, retryAfter, reason) => {
    server.use(
      http.post(CLASSIFY_URL, () =>
        HttpResponse.json(
          { detail: 'refused' },
          { status, headers: retryAfter ? { 'Retry-After': retryAfter } : {} },
        ),
      ),
    )
    const { user } = await openClassify()
    await describeAndRun(user)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(reason)
    expect(screen.getByText("The checks couldn't start")).toBeVisible()
  })

  it('keeps the description for later', async () => {
    server.use(http.post(CLASSIFY_URL, () => HttpResponse.json({}, { status: 503 })))
    const { user, router } = await openClassify()
    await describeAndRun(user)
    await user.click(await screen.findByRole('button', { name: 'Save for later' }))
    await expect.poll(() => router.state.location.pathname).toBe('/app/inventory')

    await router.navigate({ to: '/app/classify' })
    expect(await screen.findByLabelText('In your own words')).toHaveValue(
      WORKED_EXAMPLE_DESCRIPTION,
    )
  })

  it('runs in German, in German', async () => {
    let body: unknown = null
    server.use(
      classifyHandler(WORKED_EXAMPLE_EVENTS, (sent) => {
        body = sent
      }),
    )
    const { user, router } = await openClassify('de')
    expect(screen.getByRole('heading', { level: 1, name: 'Tool beschreiben' })).toBeVisible()
    await user.type(screen.getByLabelText('In Ihren eigenen Worten'), 'Ein Tool für Bewerbungen.')
    await user.click(screen.getByRole('button', { name: 'Prüfungen starten' }))
    await expect.poll(() => router.state.location.pathname).toMatch(/^\/app\/inventory\//)
    expect(body).toEqual({ description: 'Ein Tool für Bewerbungen.', language: 'de' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Ihr Tool' })).toBeVisible()
  })
})
