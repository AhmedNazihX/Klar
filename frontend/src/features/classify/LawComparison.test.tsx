import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult, ClassifyRequest } from '@/api'
import { inventoryToolsKey } from '@/hooks/use-inventory-tools'
import { anonymousSessionOptions, endAnonymousSession } from '@/hooks/use-anonymous-session'
import { originalRunKey } from '@/hooks/use-original-run'
import {
  CLASSIFY_URL,
  classifyHandler,
  decidedHighRisk,
  legacyForPublicAuthorities,
  minimalRisk,
  providerRefused,
  sseBody,
  WORKED_EXAMPLE,
  WORKED_EXAMPLE_DESCRIPTION,
} from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import {
  INTIMATE_IMAGE_DESCRIPTION,
  intimateImageAmended,
  intimateImageOriginal,
  PRESS_GUARD_DESCRIPTION,
  pressGuardAmended,
  pressGuardOriginal,
} from '@/test/original-text-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun, type ClassificationRun } from './classification-store'

const TOOL_ID = 'tool-under-two-texts'
// Axe can't compute contrast over glass in jsdom (AppFrame.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

type Open = {
  result: ClassificationResult
  description?: string
  view?: 'reviewer'
  law?: 'original'
  language?: 'en' | 'de'
  /** An original-text run already checked in this tab. */
  original?: ClassificationResult
  /** The user id of the anonymous session this tab holds. */
  session?: string
}

async function openResult({
  result,
  description = WORKED_EXAMPLE_DESCRIPTION,
  view,
  law,
  language = 'en',
  original,
  session,
}: Open) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  if (session) client.setQueryData(anonymousSessionOptions(null).queryKey, session)
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Tool under two texts',
    description,
    result,
  }
  putRun(client, run)
  if (original) client.setQueryData(originalRunKey(run), original)
  const search = new URLSearchParams()
  if (view) search.set('view', view)
  if (law) search.set('law', law)
  const query = search.toString()
  const rendered = renderRoute(`/app/inventory/${TOOL_ID}${query ? `?${query}` : ''}`, client)
  await screen.findByRole('heading', { level: 1, name: 'Tool under two texts' })
  return { ...rendered, client, user: userEvent.setup() }
}

/** Counts the `POST /classify` requests and keeps their bodies; each answers with `result`. */
function classifyReturning(result: ClassificationResult): ClassifyRequest[] {
  const bodies: ClassifyRequest[] = []
  server.use(
    classifyHandler([{ event: 'result', result }], (body) => {
      bodies.push(body as ClassifyRequest)
    }),
  )
  return bodies
}

function comparison(language: 'en' | 'de' = 'en'): HTMLElement {
  return screen.getByRole('region', {
    name: language === 'en' ? 'Original Act vs amended' : 'Ursprüngliche und geänderte Fassung',
  })
}

/** The table's rows as [label, original, amended], each value marked "-" when struck through
 *  (del) and "+" when shown as the change (ins). A value is its cell's last element: a table
 *  that can stack shows its column's name before it. */
function diffRows(panel: HTMLElement): string[][] {
  const [, ...rows] = within(panel).getAllByRole('row')
  return rows.map((row) => [
    within(row).getByRole('rowheader').textContent,
    ...within(row)
      .getAllByRole('cell')
      .map((cell) => {
        const value = cell.lastElementChild?.textContent ?? ''
        if (cell.querySelector('del')) return `-${value}`
        if (cell.querySelector('ins')) return `+${value}`
        return value
      }),
  ])
}

describe('Original Act vs amended (reviewer view)', () => {
  it('shows a case whose class differs between the texts: the ban only the Omnibus added', async () => {
    const bodies = classifyReturning(intimateImageOriginal())
    const { user } = await openResult({
      result: intimateImageAmended(),
      description: INTIMATE_IMAGE_DESCRIPTION,
      view: 'reviewer',
    })
    await user.click(
      within(comparison()).getByRole('button', { name: 'Check under the original text' }),
    )

    const panel = comparison()
    expect(await within(panel).findByText('Steps that changed')).toBeInTheDocument()
    // No date on either side: the original text's duties aren't modelled, and a ban has none.
    expect(diffRows(panel)).toEqual([
      ['Class', '-Limited risk', '+Prohibited'],
      ['Role', 'Provider', 'Provider'],
      ['Duties from', '–', '–'],
    ])
    // Only the step both runs assessed: the amended run stopped at the ban, so High-risk and
    // Transparency (reached only under the original text) and the role (the same) aren't changes.
    const steps = within(panel)
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(steps).toEqual([
      '2 Prohibited practicesOriginal: No match with a banned practice. Amended: Matches a banned practice.Changed by the Omnibus: Art. 5(1)(ba)',
    ])
    expect(panel).not.toHaveTextContent('Not checked')
    expect(panel).toHaveTextContent(
      'The values in blue changed with the Digital Omnibus, Regulation (EU) 2026/1744, in force since 27 July 2026.',
    )
    expect(panel).not.toHaveTextContent("The class didn't.")
    expect(panel).toHaveTextContent(
      "Duties under the original text aren't modelled: Klar's duty lists follow the amended text only.",
    )
    // One paid run, on the same description and date, under the original text.
    expect(bodies).toEqual([
      {
        description: INTIMATE_IMAGE_DESCRIPTION,
        language: 'en',
        law_version: 'original',
        as_of: intimateImageAmended().as_of,
      },
    ])
  })

  it('shows a route the Omnibus moved: machinery from Annex I Section A to Section B', async () => {
    await openResult({
      result: pressGuardAmended(),
      description: PRESS_GUARD_DESCRIPTION,
      view: 'reviewer',
      original: pressGuardOriginal(),
    })
    const panel = comparison()
    expect(diffRows(panel)).toEqual([
      ['Class', 'High-risk', 'High-risk'],
      ['Basis', '-Annex I Section A point 1', '+Annex I Section B point 21'],
      ['Role', 'Provider', 'Provider'],
      ['Duties from', '-2 Aug 2027', '+–'],
    ])
    const [highRisk] = within(panel).getAllByRole('listitem')
    expect(highRisk).toHaveTextContent(
      '3 High-riskOriginal: Yes: part of a product under Annex I (Annex I Section A point 1). Amended: Yes: part of a product under Annex I (Annex I Section B point 21).Changed by the Omnibus: Annex I Section B point 21, Art. 2(2)',
    )
    expect(panel).toHaveTextContent(
      "The values in blue changed with the Digital Omnibus, Regulation (EU) 2026/1744, in force since 27 July 2026. The class didn't.",
    )
  })

  it('before the original text is checked, shows only the moved date and sends nothing', async () => {
    const bodies = classifyReturning(intimateImageOriginal())
    await openResult({ result: decidedHighRisk(), view: 'reviewer' })
    const panel = comparison()
    expect(diffRows(panel)).toEqual([
      ['Class', 'Not checked yet', 'High-risk'],
      ['Role', 'Not checked yet', 'Deployer'],
      ['Duties from', '-2 Aug 2026', '+2 Dec 2027'],
    ])
    // The note says only what is known: the date moved; the class isn't checked yet.
    expect(panel).toHaveTextContent(
      "The date in blue changed with the Digital Omnibus, Regulation (EU) 2026/1744, in force since 27 July 2026. Klar hasn't checked the class and role under the original text yet.",
    )
    expect(panel).not.toHaveTextContent('Nothing in this table changed')
    expect(
      within(panel).getByRole('button', { name: 'Check under the original text' }),
    ).toBeEnabled()
    expect(bodies).toHaveLength(0)
  })

  it.each([
    [
      'en',
      'Not checked yet',
      "Klar hasn't checked the class and role under the original text yet.",
    ],
    [
      'de',
      'Noch nicht geprüft',
      'Klasse und Rolle nach der ursprünglichen Fassung hat Klar noch nicht geprüft.',
    ],
  ] as const)(
    'before the check, with no route date to swap, claims no change and fills no date (%s)',
    async (language, notChecked, note) => {
      await openResult({
        result: intimateImageAmended(),
        description: INTIMATE_IMAGE_DESCRIPTION,
        view: 'reviewer',
        language,
      })
      const panel = comparison(language)
      // The original column holds no value it doesn't know: only a route's Art. 113 date could be.
      expect(diffRows(panel).map((row) => row.slice(1))).toEqual([
        [notChecked, language === 'en' ? 'Prohibited' : 'Verboten'],
        [notChecked, language === 'en' ? 'Provider' : 'Anbieter'],
        [notChecked, '–'],
      ])
      expect(within(panel).getByText(note)).toBeInTheDocument()
      expect(panel).not.toHaveTextContent(/Nothing in this table|nichts geändert|blue|blau/)
    },
  )

  it('keeps the Art. 111(2) date of a legacy system for public authorities under both texts', async () => {
    const original = {
      ...legacyForPublicAuthorities(),
      law_version: 'original' as const,
      obligations: [],
    }
    await openResult({ result: legacyForPublicAuthorities(), view: 'reviewer', original })
    const panel = comparison()
    expect(diffRows(panel).at(-1)).toEqual(['Duties from', '2 Aug 2030', '2 Aug 2030'])
    expect(panel).toHaveTextContent(
      'Nothing in this table changed with the Digital Omnibus, Regulation (EU) 2026/1744, in force since 27 July 2026.',
    )
  })

  it('before the check of a legacy system for public authorities, leaves its date unchecked', async () => {
    await openResult({ result: legacyForPublicAuthorities(), view: 'reviewer' })
    expect(diffRows(comparison()).at(-1)).toEqual(['Duties from', 'Not checked yet', '2 Aug 2030'])
  })

  it("says when nothing changed, and that the class didn't", async () => {
    const original = { ...decidedHighRisk(), law_version: 'original' as const, obligations: [] }
    await openResult({ result: decidedHighRisk(), view: 'reviewer', original })
    const panel = comparison()
    expect(diffRows(panel)[0]).toEqual(['Class', 'High-risk', 'High-risk'])
    expect(
      within(panel).getByText("No step's outcome differs between the two texts."),
    ).toBeInTheDocument()
    // The route date still moved, so the note names the Omnibus's change and keeps the class.
    expect(panel).toHaveTextContent("The class didn't.")
  })

  it('a stopped run shows why, shows no original class, and runs again only on Try again', async () => {
    let requests = 0
    server.use(
      http.post(CLASSIFY_URL, () => {
        requests += 1
        return HttpResponse.json({}, { status: 503 })
      }),
    )
    const { user } = await openResult({ result: intimateImageAmended(), view: 'reviewer' })
    await user.click(
      within(comparison()).getByRole('button', { name: 'Check under the original text' }),
    )
    const alert = await within(comparison()).findByRole('alert')
    expect(alert).toHaveTextContent(
      "The check under the original text stopped. The checks aren't available right now. Try again later.",
    )
    expect(diffRows(comparison())[0]).toEqual(['Class', 'Not checked yet', 'Prohibited'])
    expect(requests).toBe(1)
    await user.click(within(comparison()).getByRole('button', { name: 'Try again' }))
    await within(comparison()).findByRole('alert')
    expect(requests).toBe(2)
  })

  it('reads the same in German', async () => {
    await openResult({
      result: intimateImageAmended(),
      description: INTIMATE_IMAGE_DESCRIPTION,
      view: 'reviewer',
      language: 'de',
      original: intimateImageOriginal(),
    })
    const panel = comparison('de')
    expect(
      within(panel)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual(['Ursprünglich', 'Geändert'])
    expect(diffRows(panel)).toEqual([
      ['Klasse', '-Begrenztes Risiko', '+Verboten'],
      ['Rolle', 'Anbieter', 'Anbieter'],
      ['Pflichten ab', '–', '–'],
    ])
    expect(within(panel).getByText('Geänderte Prüfschritte')).toBeInTheDocument()
    expect(within(panel).getAllByRole('listitem')[0]).toHaveTextContent(
      '2 Verbotene PraktikenUrsprünglich: Kein Treffer bei den verbotenen Praktiken. Geändert: Entspricht einer verbotenen Praktik.Vom Omnibus geändert: Art. 5 Abs. 1 Buchst. ba',
    )
    expect(panel).toHaveTextContent(
      'Die blau markierten Werte hat der digitale Omnibus geändert, die Verordnung (EU) 2026/1744, in Kraft seit dem 27. Juli 2026.',
    )
    expect(panel).toHaveTextContent(
      'Pflichten nach der ursprünglichen Fassung sind nicht modelliert: Klars Pflichtenlisten folgen nur der geänderten Fassung.',
    )
  })

  it('German before the check: the button, its hint and the note', async () => {
    await openResult({ result: decidedHighRisk(), view: 'reviewer', language: 'de' })
    const panel = comparison('de')
    expect(
      within(panel).getByRole('button', { name: 'Nach ursprünglicher Fassung prüfen' }),
    ).toBeEnabled()
    expect(panel).toHaveTextContent(
      'Klar kann die Prüfungen mit derselben Beschreibung nach der ursprünglichen Fassung von 2024 wiederholen. Dieses Ergebnis wird nicht in Ihrem Inventar gespeichert.',
    )
    expect(panel).toHaveTextContent(
      'Das blau markierte Datum hat der digitale Omnibus geändert, die Verordnung (EU) 2026/1744, in Kraft seit dem 27. Juli 2026. Klasse und Rolle nach der ursprünglichen Fassung hat Klar noch nicht geprüft.',
    )
    expect(diffRows(panel)[0]).toEqual(['Klasse', 'Noch nicht geprüft', 'Hochrisiko'])
  })

  it('has no comparison on a result run under the original text', async () => {
    await openResult({ result: intimateImageOriginal(), view: 'reviewer' })
    expect(screen.queryByRole('region', { name: 'Original Act vs amended' })).toBeNull()
  })

  it('passes axe with the comparison filled', async () => {
    const { container } = await openResult({
      result: intimateImageAmended(),
      view: 'reviewer',
      original: intimateImageOriginal(),
    })
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])
  })
})

describe('The summary under the original text', () => {
  const DATES_NOTICE =
    "Dates follow the original Art. 113. The duties shown are the amended text's."

  it("keeps the amended duty list, with the notice that only Art. 113's dates follow the switch", async () => {
    await openResult({ result: decidedHighRisk(), law: 'original' })
    const todo = screen.getByRole('region', { name: 'What you need to do' })
    expect(within(todo).getByRole('note')).toHaveTextContent(DATES_NOTICE)
    expect(within(todo).getAllByRole('listitem').length).toBeGreaterThan(0)
  })

  it('shows the dates notice once, also with the Duties step open', async () => {
    const { user } = await openResult({ result: decidedHighRisk(), law: 'original' })
    const steps = screen.getByRole('region', { name: 'How Klar got here' })
    const row = within(steps)
      .getAllByRole('button', { expanded: false })
      .find((button) => button.textContent.startsWith('Duties'))
    if (!row) throw new Error('The steps list has a Duties row.')
    await user.click(row)
    expect(row).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getAllByText(DATES_NOTICE)).toHaveLength(1)
  })

  it('shows no such notice under the amended text', async () => {
    await openResult({ result: decidedHighRisk() })
    expect(screen.queryByText(DATES_NOTICE)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Compare the two texts' })).toBeNull()
  })

  it("says the class is the amended text's until the original is checked, and links to the comparison", async () => {
    const { user, router } = await openResult({ result: decidedHighRisk(), law: 'original' })
    expect(
      screen.getByText(
        'This page shows the class under the amended text. To see the class under the original 2024 text, compare the two texts.',
      ),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Compare the two texts' }))
    expect(router.state.location.search).toEqual({ law: 'original', view: 'reviewer' })
    expect(
      await screen.findByRole('region', { name: 'Original Act vs amended' }),
    ).toBeInTheDocument()
  })

  it('names the original class when the original run found another one', async () => {
    await openResult({
      result: intimateImageAmended(),
      description: INTIMATE_IMAGE_DESCRIPTION,
      law: 'original',
      original: intimateImageOriginal(),
    })
    expect(
      screen.getByText(
        "Under the original 2024 text, Klar finds: Limited risk. This page shows the amended text's result.",
      ),
    ).toBeInTheDocument()
  })

  it('names the other basis when the class stayed but the Annex point moved', async () => {
    await openResult({
      result: pressGuardAmended(),
      description: PRESS_GUARD_DESCRIPTION,
      law: 'original',
      original: pressGuardOriginal(),
    })
    expect(
      screen.getByText(
        'Under the original 2024 text, the class is the same (High-risk), on another basis: Annex I Section A point 1.',
      ),
    ).toBeInTheDocument()
  })

  it('reads the same in German', async () => {
    await openResult({
      result: intimateImageAmended(),
      description: INTIMATE_IMAGE_DESCRIPTION,
      law: 'original',
      language: 'de',
      original: intimateImageOriginal(),
    })
    expect(
      screen.getByText(
        'Nach der ursprünglichen Fassung von 2024 kommt Klar zu: Begrenztes Risiko. Diese Seite zeigt das Ergebnis nach der geänderten Fassung.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Beide Fassungen vergleichen' })).toBeInTheDocument()
  })

  it('German: the duty list notice, and the class line before a check', async () => {
    await openResult({ result: decidedHighRisk(), law: 'original', language: 'de' })
    const todo = screen.getByRole('region', { name: 'Was Sie tun müssen' })
    expect(within(todo).getByRole('note')).toHaveTextContent(
      'Die Daten folgen dem ursprünglichen Art. 113. Die angezeigten Pflichten sind die der geänderten Fassung.',
    )
    expect(
      screen.getByText(
        'Diese Seite zeigt die Klasse nach der geänderten Fassung. Um die Klasse nach der ursprünglichen Fassung von 2024 zu sehen, vergleichen Sie die beiden Fassungen.',
      ),
    ).toBeInTheDocument()
  })

  it.each([
    [
      'en',
      "Duties not modelled for the original text: Klar's duty lists cover only the amended text, so none are listed.",
    ],
    [
      'de',
      'Pflichten für die ursprüngliche Fassung nicht modelliert: Klars Pflichtenlisten decken nur die geänderte Fassung ab, daher sind keine aufgeführt.',
    ],
  ] as const)(
    'a result run under the original text says its duties are not modelled (%s)',
    async (language, sentence) => {
      await openResult({ result: pressGuardOriginal(), language })
      expect(screen.getByText(sentence)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Compare|vergleichen/ })).toBeNull()
    },
  )
})

describe('Original Act vs amended, the remaining lines', () => {
  it('says nothing changed when nothing in the table did (en)', async () => {
    const original = { ...minimalRisk(), law_version: 'original' as const, obligations: [] }
    await openResult({ result: minimalRisk(), view: 'reviewer', original })
    expect(comparison()).toHaveTextContent(
      'Nothing in this table changed with the Digital Omnibus, Regulation (EU) 2026/1744, in force since 27 July 2026.',
    )
    expect(comparison()).not.toHaveTextContent("The class didn't.")
  })

  it('says the same in German, with no step changed', async () => {
    const original = { ...minimalRisk(), law_version: 'original' as const, obligations: [] }
    await openResult({ result: minimalRisk(), view: 'reviewer', language: 'de', original })
    const panel = comparison('de')
    expect(panel).toHaveTextContent(
      'Der digitale Omnibus, die Verordnung (EU) 2026/1744, in Kraft seit dem 27. Juli 2026, hat an dieser Tabelle nichts geändert.',
    )
    expect(
      within(panel).getByText(
        'Kein Prüfschritt kommt nach den beiden Fassungen zu einem anderen Ergebnis.',
      ),
    ).toBeInTheDocument()
  })

  it('German: the class kept, on another basis, and "the class didn\'t"', async () => {
    await openResult({
      result: pressGuardAmended(),
      description: PRESS_GUARD_DESCRIPTION,
      view: 'reviewer',
      language: 'de',
      original: pressGuardOriginal(),
    })
    const panel = comparison('de')
    expect(diffRows(panel)[1]).toEqual([
      'Grundlage',
      '-Anhang I Abschnitt A Nr. 1',
      '+Anhang I Abschnitt B Nr. 21',
    ])
    expect(panel).toHaveTextContent('Die Klasse ist gleich geblieben.')
  })

  it.each([
    [
      'en',
      'Under the original 2024 text, the class is the same: High-risk.',
      'Under the original 2024 text, the class is the same (High-risk), on another basis: Annex I Section A point 1.',
    ],
    [
      'de',
      'Nach der ursprünglichen Fassung von 2024 ist die Klasse gleich: Hochrisiko.',
      'Nach der ursprünglichen Fassung von 2024 ist die Klasse gleich (Hochrisiko), mit anderer Grundlage: Anhang I Abschnitt A Nr. 1.',
    ],
  ] as const)(
    'the summary names a kept class, and a kept class on another basis (%s)',
    async (language, same, otherBasis) => {
      const original = { ...decidedHighRisk(), law_version: 'original' as const, obligations: [] }
      const first = await openResult({
        result: decidedHighRisk(),
        law: 'original',
        language,
        original,
      })
      expect(screen.getByText(same)).toBeInTheDocument()
      first.unmount()
      await openResult({
        result: pressGuardAmended(),
        description: PRESS_GUARD_DESCRIPTION,
        law: 'original',
        language,
        original: pressGuardOriginal(),
      })
      expect(screen.getByText(otherBasis)).toBeInTheDocument()
    },
  )

  it.each([
    ['en', 'Checking under the original text…', 'Check under the original text'],
    ['de', 'Prüfung nach ursprünglicher Fassung läuft …', 'Nach ursprünglicher Fassung prüfen'],
  ] as const)(
    'while the run streams, the button says so and can not start a second run (%s)',
    async (language, running, start) => {
      let requests = 0
      server.use(
        http.post(CLASSIFY_URL, async () => {
          requests += 1
          await delay('infinite')
          return HttpResponse.json({})
        }),
      )
      const { user } = await openResult({ result: decidedHighRisk(), view: 'reviewer', language })
      const panel = comparison(language)
      await user.click(within(panel).getByRole('button', { name: start }))
      const busy = await within(panel).findByRole('button', { name: running })
      expect(busy).toBeDisabled()
      expect(requests).toBe(1)
    },
  )

  it.each([
    [
      'en',
      'High-risk, assumed',
      "Klar can run the checks again on the same description under the original 2024 text. That result isn't saved to your inventory.",
    ],
    [
      'de',
      'Hochrisiko, angenommen',
      'Klar kann die Prüfungen mit derselben Beschreibung nach der ursprünglichen Fassung von 2024 wiederholen. Dieses Ergebnis wird nicht in Ihrem Inventar gespeichert.',
    ],
  ] as const)(
    'labels an assumed class as assumed, and says the run is not saved (%s)',
    async (language, assumed, hint) => {
      await openResult({ result: WORKED_EXAMPLE, view: 'reviewer', language })
      const panel = comparison(language)
      expect(diffRows(panel)[0]?.[2]).toBe(assumed)
      expect(panel).toHaveTextContent(hint)
    },
  )

  it.each([
    [
      'en',
      'Check under the original text',
      "The model provider's content filter blocked the check under the original 2024 text, so Klar can't compare the class and role under it. Your result under the amended text still stands.",
      'Klar can run the checks again',
      "Klar couldn't check the class and role under the original text.",
      'Not checked',
      "Klar hasn't checked the class and role under the original text yet.",
    ],
    [
      'de',
      'Nach ursprünglicher Fassung prüfen',
      'Der Inhaltsfilter des Modellanbieters hat die Prüfung nach der ursprünglichen Fassung von 2024 blockiert, deshalb kann Klar Einstufung und Rolle danach nicht vergleichen. Ihr Ergebnis nach der geänderten Fassung gilt weiter.',
      'Klar kann die Prüfungen',
      'Klasse und Rolle nach der ursprünglichen Fassung konnte Klar nicht prüfen.',
      'Nicht geprüft',
      'Klasse und Rolle nach der ursprünglichen Fassung hat Klar noch nicht geprüft.',
    ],
  ] as const)(
    'offers no new run once the provider refused the original-text check (%s)',
    async (language, start, refused, hint, note, cell, notYet) => {
      const bodies = classifyReturning(providerRefused())
      const { user } = await openResult({ result: decidedHighRisk(), view: 'reviewer', language })
      await user.click(within(comparison(language)).getByRole('button', { name: start }))
      const alert = await within(comparison(language)).findByRole('alert')
      expect(alert).toHaveTextContent(refused)
      // Nothing says the checks can run again under the original text, or will check it yet.
      expect(comparison(language)).not.toHaveTextContent(hint)
      expect(comparison(language)).toHaveTextContent(note)
      expect(comparison(language)).not.toHaveTextContent(notYet)
      expect(
        diffRows(comparison(language))
          .map((row) => row[1])
          .slice(0, 2),
      ).toEqual([cell, cell])
      expect(within(comparison(language)).queryByRole('button')).toBeNull()
      expect(bodies).toHaveLength(1)
    },
  )

  it('German: a stopped run says why', async () => {
    server.use(http.post(CLASSIFY_URL, () => HttpResponse.json({}, { status: 503 })))
    const { user } = await openResult({
      result: decidedHighRisk(),
      view: 'reviewer',
      language: 'de',
    })
    await user.click(
      within(comparison('de')).getByRole('button', { name: 'Nach ursprünglicher Fassung prüfen' }),
    )
    expect(await within(comparison('de')).findByRole('alert')).toHaveTextContent(
      'Die Prüfung nach der ursprünglichen Fassung wurde angehalten. Die Prüfungen sind gerade nicht verfügbar. Versuchen Sie es später erneut.',
    )
    expect(within(comparison('de')).getByRole('button', { name: 'Erneut versuchen' })).toBeEnabled()
  })
})

/** A classify request held open until `release`: the run streams its result only then. */
function classifyHeld(result: ClassificationResult): {
  release: () => void
  requests: () => number
} {
  let release = (): void => undefined
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let count = 0
  server.use(
    http.post(CLASSIFY_URL, async () => {
      count += 1
      await gate
      return new HttpResponse(sseBody([{ event: 'result', result }]), {
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }),
  )
  return {
    release: () => {
      release()
    },
    requests: () => count,
  }
}

describe('The law switch and the original-text run', () => {
  const DATES_NOTICE =
    "Dates follow the original Art. 113. The duties shown are the amended text's."

  it('switching the law on a result keeps the screen, the view and the result, and sends nothing', async () => {
    const bodies = classifyReturning(intimateImageOriginal())
    const { user, router } = await openResult({ result: decidedHighRisk(), view: 'reviewer' })
    const group = screen.getByRole('group', { name: 'Law version' })
    // The top bar's labels hold a phone and a wide variant, both in the accessible name.
    await user.click(within(group).getByRole('button', { name: /Original, 2024/ }))
    expect(router.state.location.pathname).toBe(`/app/inventory/${TOOL_ID}`)
    expect(router.state.location.search).toEqual({ view: 'reviewer', law: 'original' })
    expect(comparison()).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Tool under two texts' })).toBeVisible()
    await user.click(within(group).getByRole('button', { name: /As amended, 27 Jul 2026/ }))
    expect(router.state.location.search).toEqual({ view: 'reviewer' })
    expect(comparison()).toBeInTheDocument()
    expect(bodies).toHaveLength(0)
  })

  it.each([
    ['the summary', undefined],
    ['the reviewer view', 'reviewer'],
  ] as const)(
    'opening %s under the original text, with no original run, sends no paid request',
    async (_, view) => {
      const bodies = classifyReturning(intimateImageOriginal())
      await openResult({ result: decidedHighRisk(), law: 'original', view })
      expect((await screen.findAllByText(DATES_NOTICE)).length).toBeGreaterThan(0)
      expect(bodies).toHaveLength(0)
    },
  )

  it('opening the inventory under the original text sends no paid request', async () => {
    const bodies = classifyReturning(intimateImageOriginal())
    const client = createTestQueryClient()
    client.setQueryData(inventoryToolsKey, [
      {
        toolId: TOOL_ID,
        name: 'Tool under two texts',
        description: WORKED_EXAMPLE_DESCRIPTION,
        createdAt: '2026-10-01T09:00:00+00:00',
        result: decidedHighRisk(),
        hasUnreadableResult: false,
        runNo: 1,
      },
    ])
    renderRoute('/app/inventory?law=original', client)
    expect(await screen.findByRole('link', { name: 'Tool under two texts' })).toBeInTheDocument()
    expect(bodies).toHaveLength(0)
  })

  it('a run started in the reviewer view goes on while the summary shows, and keeps its answer', async () => {
    const held = classifyHeld(intimateImageOriginal())
    const { user } = await openResult({
      result: intimateImageAmended(),
      description: INTIMATE_IMAGE_DESCRIPTION,
      view: 'reviewer',
      law: 'original',
    })
    await user.click(
      within(comparison()).getByRole('button', { name: 'Check under the original text' }),
    )
    await within(comparison()).findByRole('button', { name: 'Checking under the original text…' })
    await user.click(screen.getByRole('button', { name: 'Summary' }))
    held.release()
    expect(
      await screen.findByText(
        "Under the original 2024 text, Klar finds: Limited risk. This page shows the amended text's result.",
      ),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reviewer' }))
    expect(diffRows(comparison())[0]).toEqual(['Class', '-Limited risk', '+Prohibited'])
    expect(held.requests()).toBe(1)
  })

  it.each([
    ['kept while the session is the same', false, '-Limited risk'],
    ['dropped once the session ended (sign-out, Delete my data)', true, 'Not checked yet'],
  ] as const)("a run's answer is %s", async (_, endsSession, originalClass) => {
    const held = classifyHeld(intimateImageOriginal())
    const { user, client } = await openResult({
      result: intimateImageAmended(),
      description: INTIMATE_IMAGE_DESCRIPTION,
      view: 'reviewer',
      session: 'user-1',
    })
    await user.click(
      within(comparison()).getByRole('button', { name: 'Check under the original text' }),
    )
    await within(comparison()).findByRole('button', { name: 'Checking under the original text…' })
    if (endsSession) endAnonymousSession(client)
    held.release()
    // The run has ended either way: the button is back, or the comparison is filled.
    await within(comparison()).findByText(
      endsSession ? 'Check under the original text' : 'Steps that changed',
    )
    expect(diffRows(comparison())[0]?.[1]).toBe(originalClass)
  })

  it('"Compare the two texts" moves the focus to the comparison', async () => {
    const { user } = await openResult({ result: decidedHighRisk(), law: 'original' })
    await user.click(screen.getByRole('button', { name: 'Compare the two texts' }))
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Original Act vs amended' }),
    ).toHaveFocus()
  })

  it('leaves the comparison unfocused when the reviewer view comes back later', async () => {
    const { user, router } = await openResult({ result: decidedHighRisk(), law: 'original' })
    await user.click(screen.getByRole('button', { name: 'Compare the two texts' }))
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Original Act vs amended' }),
    ).toHaveFocus()
    // The view changes by the address (a link, the history), not by the view switch.
    const path = `/app/inventory/${TOOL_ID}?law=original`
    act(() => {
      router.history.push(path)
    })
    await screen.findByRole('button', { name: 'Compare the two texts' })
    act(() => {
      router.history.push(`${path}&view=reviewer`)
    })
    const heading = await screen.findByRole('heading', {
      level: 2,
      name: 'Original Act vs amended',
    })
    expect(heading).not.toHaveFocus()
  })

  it.each([
    ['en', DATES_NOTICE],
    [
      'de',
      'Die Daten folgen dem ursprünglichen Art. 113. Die angezeigten Pflichten sind die der geänderten Fassung.',
    ],
  ] as const)(
    "the reviewer view's duty list says its dates follow Art. 113 under the original text (%s)",
    async (language, notice) => {
      const first = await openResult({
        result: decidedHighRisk(),
        view: 'reviewer',
        law: 'original',
        language,
      })
      expect(screen.getByText(notice)).toBeInTheDocument()
      first.unmount()
      await openResult({ result: decidedHighRisk(), view: 'reviewer', language })
      expect(screen.queryByText(notice)).toBeNull()
    },
  )

  it('German summary: a route date that has come under the original text says so', async () => {
    await openResult({ result: decidedHighRisk(), law: 'original', language: 'de' })
    expect(screen.getByText('Gilt nach der ursprünglichen Fassung bereits')).toBeInTheDocument()
  })
})
