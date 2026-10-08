import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult, ClassifyRequest } from '@/api'
import { originalRunKey } from '@/hooks/use-original-run'
import {
  CLASSIFY_URL,
  classifyHandler,
  decidedHighRisk,
  minimalRisk,
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
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

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
}

async function openResult({
  result,
  description = WORKED_EXAMPLE_DESCRIPTION,
  view,
  law,
  language = 'en',
  original,
}: Open) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
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
  await screen.findByRole(
    'heading',
    { level: 1, name: 'Tool under two texts' },
    { timeout: FIRST_RENDER_MS },
  )
  return { ...rendered, user: userEvent.setup() }
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
 *  (del) and "+" when shown as the change (ins). */
function diffRows(panel: HTMLElement): string[][] {
  const [, ...rows] = within(panel).getAllByRole('row')
  return rows.map((row) => {
    const [label, ...cells] = Array.from(row.children)
    return [
      label?.textContent ?? '',
      ...cells.map((cell) => {
        if (cell.querySelector('del')) return `-${cell.textContent}`
        if (cell.querySelector('ins')) return `+${cell.textContent}`
        return cell.textContent
      }),
    ]
  })
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
    expect(diffRows(panel)).toEqual([
      ['Class', '-Limited risk', '+Prohibited'],
      ['Role', 'Provider', 'Provider'],
      ['Duties from', '-Not modelled', '+No duties listed'],
    ])
    const steps = within(panel)
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(steps[0]).toBe(
      '2 Prohibited practicesOriginal: No match with a banned practice. Amended: Matches a banned practice.Changed by the Omnibus: Art. 5(1)(ba)',
    )
    expect(steps).toHaveLength(4)
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
      ['Duties from', '-2 Aug 2027', '+No duties listed'],
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
    expect(panel).toHaveTextContent(
      'The values in blue changed with the Digital Omnibus, Regulation (EU) 2026/1744, in force since 27 July 2026. The class and role under the original text show once Klar has checked it.',
    )
    expect(
      within(panel).getByRole('button', { name: 'Check under the original text' }),
    ).toBeEnabled()
    expect(bodies).toHaveLength(0)
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
      ['Pflichten ab', '-Nicht modelliert', '+Keine Pflichten aufgeführt'],
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
      'Klasse und Rolle nach der ursprünglichen Fassung erscheinen, sobald Klar sie geprüft hat.',
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
