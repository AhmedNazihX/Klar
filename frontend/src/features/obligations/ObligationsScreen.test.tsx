import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import { env } from '@/lib/env'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  decidedHighRisk,
  legacyForPublicAuthorities,
  legacyMarkedDeployer,
  limitedRisk,
  minimalRisk,
  outOfScope,
  WORKED_EXAMPLE,
} from '@/test/classify-fixtures'
import { ambiguousResult, prohibitedResult, toolRow } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { SUPABASE_URL } from '@/test/supabase-fixtures'
import { renderRoute } from '@/test/test-utils'
import { inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

// The app's Supabase client, pointed at the MSW network boundary.
vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL: url } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url, anonKey: 'test-anon-key' }),
  }
})

const DUTY_PROGRESS_URL = `${SUPABASE_URL}/rest/v1/duty_progress`
const CHECKLIST_URL = `${env.apiUrl}/reports/checklist`

/** After Art. 50 started to apply (2 Aug 2026), before the amended Annex III date. */
const TODAY = new Date(2026, 9, 7, 12)

const INSTRUCTIONS = "Use the tool as the vendor's instructions say"
const NOT_CHECKED = "Klar keeps the list; it doesn't check the work for you."

type Tick = { system_id: string; obligation_key: string }

let tools: Record<string, unknown>[] = []
/** The company profile's size class (P31's relief notes). */
let sizeClass: 'sme' | 'smc' | 'none' | null = null
let ticks: Tick[] = []
let writes: string[] = []
let checklists: unknown[] = []
let downloads: string[] = []

/** duty_progress through PostgREST: read the ticks, insert one, delete one by its filters. */
function dutyProgressHandlers(failWrites = false) {
  return [
    http.get(DUTY_PROGRESS_URL, () => HttpResponse.json(ticks)),
    http.post(DUTY_PROGRESS_URL, async ({ request }) => {
      const tick = (await request.json()) as Tick
      writes.push(`add ${tick.obligation_key}`)
      if (failWrites) return HttpResponse.json({ message: 'refused' }, { status: 500 })
      ticks = [...ticks, tick]
      return new HttpResponse(null, { status: 201 })
    }),
    http.delete(DUTY_PROGRESS_URL, ({ request }) => {
      const params = new URL(request.url).searchParams
      const key = params.get('obligation_key')?.replace(/^eq\./, '')
      const system = params.get('system_id')?.replace(/^eq\./, '')
      writes.push(`remove ${key ?? ''}`)
      ticks = ticks.filter((tick) => tick.obligation_key !== key || tick.system_id !== system)
      return new HttpResponse(null, { status: 204 })
    }),
  ]
}

beforeAll(() => {
  // jsdom has no object URLs; these stand in for the browser's.
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: () => 'blob:klar' })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: () => undefined })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloads.push(this.download)
  })
})

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(TODAY)
  tools = []
  sizeClass = null
  ticks = []
  writes = []
  checklists = []
  downloads = []
  server.use(
    ...userDataHandlers(
      () => [inventoryRow({ company_name: 'Nordwerk Logistik GmbH', size_class: sizeClass })],
      () => tools.length,
      () => tools,
    ),
    ...dutyProgressHandlers(),
    http.post(CHECKLIST_URL, async ({ request }) => {
      checklists.push(await request.json())
      return new HttpResponse(new Blob(['PK']), {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        },
      })
    }),
  )
})
afterEach(() => {
  vi.useRealTimers()
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

async function openObligations(path = '/app/obligations', language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute(path)
  await screen.findByRole('heading', { level: 1 })
  await screen.findByRole('region', { name: /^(Progress|Fortschritt)$/ })
  return { user, ...rendered }
}

function section(name: string | RegExp): HTMLElement {
  return screen.getByRole('region', { name })
}

function progressLine(): string | null {
  return section('Progress').querySelector('h2 + span')?.textContent ?? null
}

/** The names of every duty box on the screen, after opening every "Show all". */
async function allBoxes(user: ReturnType<typeof userEvent.setup>): Promise<string[]> {
  for (const button of screen.queryAllByRole('button', { name: /^Show all/ })) {
    await user.click(button)
  }
  return screen
    .getAllByRole('checkbox')
    .map((box) => box.getAttribute('aria-label') ?? '')
    .sort()
}

function withRouteDuties(
  result: ClassificationResult,
  change: Partial<NonNullable<ClassificationResult['obligations']>[number]>,
): ClassificationResult {
  return {
    ...result,
    obligations: (result.obligations ?? []).map((duty) =>
      duty.high_risk_route ? { ...duty, ...change } : duty,
    ),
  }
}

describe('Obligations, ticking duties', () => {
  it('saves a tick, and the counts per tool and overall change; clearing it deletes it', async () => {
    const screening = toolRow('Applicant screening', decidedHighRisk())
    tools = [screening]
    const { user } = await openObligations()
    const route = section(/^From 2 December 2027/)
    expect(within(route).getByText('0 of 10 done')).toBeInTheDocument()
    expect(progressLine()).toBe('0 of 11 done')
    expect(screen.getByRole('progressbar', { name: 'Duties done' })).toHaveAttribute(
      'aria-valuenow',
      '0',
    )

    const box = within(route).getByRole('checkbox', { name: INSTRUCTIONS })
    await user.click(box)
    await vi.waitFor(() => expect(writes).toEqual(['add hr-deployer-instructions']))
    expect(ticks).toEqual([
      { system_id: screening['id'], obligation_key: 'hr-deployer-instructions' },
    ])
    await vi.waitFor(() => expect(progressLine()).toBe('1 of 11 done'))
    expect(box).toBeChecked()
    expect(within(route).getByText('1 of 10 done')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Duties done' })).toHaveAttribute(
      'aria-valuenow',
      '1',
    )

    await user.click(box)
    await vi.waitFor(() =>
      expect(writes).toEqual(['add hr-deployer-instructions', 'remove hr-deployer-instructions']),
    )
    await vi.waitFor(() => expect(progressLine()).toBe('0 of 11 done'))
    expect(box).not.toBeChecked()
    expect(ticks).toEqual([])
  })

  it('shows the saved ticks, and says Klar does not check the work wherever progress shows', async () => {
    const screening = toolRow('Applicant screening', decidedHighRisk())
    tools = [screening]
    ticks = [{ system_id: String(screening['id']), obligation_key: 'ai-literacy' }]
    await openObligations()
    const literacy = section('In force since 2 February 2025')
    expect(
      within(literacy).getByRole('checkbox', {
        name: 'Help the people who run or use it build their AI literacy',
      }),
    ).toBeChecked()
    expect(progressLine()).toBe('1 of 11 done')
    expect(section('Progress')).toHaveTextContent(`Tick duties off as you go. ${NOT_CHECKED}`)
    expect(screen.getAllByText(NOT_CHECKED).length).toBeGreaterThan(0)
  })

  it('puts the box back and says so when the tick is not saved', async () => {
    server.use(...dutyProgressHandlers(true))
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    const { user } = await openObligations()
    const box = screen.getByRole('checkbox', { name: INSTRUCTIONS })
    await user.click(box)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Klar couldn't save that tick. Please try again.",
    )
    await vi.waitFor(() => expect(box).not.toBeChecked())
    expect(writes).toEqual(['add hr-deployer-instructions'])
  })
})

describe('Obligations, By date and By tool', () => {
  it('groups by date, and By tool regroups the same duties under each tool', async () => {
    tools = [
      toolRow('Applicant screening', decidedHighRisk()),
      toolRow('Call mood scoring', prohibitedResult()),
      toolRow('Product photo generator', limitedRisk()),
      toolRow('Route optimisation', minimalRisk()),
      toolRow('Invoice matching', outOfScope()),
    ]
    const { user, router } = await openObligations()
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'Stop now',
      'In force since 2 February 2025',
      'In force since 2 August 2026',
      'From 2 December 20272 August 2026',
      'No specific duties',
      'Next date',
      'Progress',
      'Take the checklist with you',
    ])
    expect(section('Stop now')).toHaveTextContent('Stop using or supplying it now')
    expect(
      within(section('No specific duties'))
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Route optimisationMinimal risk', 'Invoice matchingOut of scope'])
    const byDate = await allBoxes(user)

    await user.click(screen.getByRole('button', { name: 'By tool' }))
    await vi.waitFor(() => expect(router.state.location.search).toEqual({ group: 'tool' }))
    expect(
      screen
        .getAllByRole('link', { name: /^(Applicant|Call|Product|Route|Invoice)/ })
        .map((link) => link.textContent),
    ).toEqual([
      'Call mood scoring',
      'Applicant screening',
      'Product photo generator',
      'Route optimisation',
      'Invoice matching',
    ])
    // A tool without duties has its card too, as By date lists it under No specific duties.
    const invoices = screen.getByRole('link', { name: 'Invoice matching' }).closest('[data-tone]')
    expect(invoices).toHaveTextContent('Invoice matchingOut of scopeNo specific duties')
    expect(await allBoxes(user)).toEqual(byDate)
  })

  it('opens By tool from a shared link', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    await openObligations('/app/obligations?group=tool')
    expect(screen.getByRole('button', { name: 'By tool' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('heading', { name: /^From/ })).not.toBeInTheDocument()
  })

  it('shows the first four duties of a tool until Show all', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    const { user } = await openObligations()
    const route = section(/^From 2 December 2027/)
    expect(within(route).getAllByRole('checkbox')).toHaveLength(4)
    // The count beside it is over the same ten duties.
    expect(within(route).getByText('0 of 10 done')).toBeInTheDocument()
    await user.click(within(route).getByRole('button', { name: 'Show all 10 duties' }))
    expect(within(route).getAllByRole('checkbox')).toHaveLength(10)
    expect(within(route).getByRole('button', { name: 'Show fewer' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it.each([
    ['en', 'Show 6 more', '0 of 9 done'],
    ['de', '6 weitere zeigen', '0 von 9 erledigt'],
  ] as const)(
    '(%s) counts the hidden lines when one has nothing to tick, so the link and count never clash',
    async (language, more, done) => {
      // One of the ten route duties is information only: nine to tick, ten lines.
      const result = decidedHighRisk()
      const informational = (result.obligations ?? []).find((duty) => duty.high_risk_route)
      tools = [
        toolRow('Applicant screening', {
          ...result,
          obligations: (result.obligations ?? []).map((duty) =>
            duty === informational ? { ...duty, is_informational: true } : duty,
          ),
        }),
      ]
      await openObligations('/app/obligations', language)
      const route = section(
        language === 'en' ? /^From 2 December 2027/ : /^Ab dem 2\. Dezember 2027/,
      )
      expect(within(route).getByText(done)).toBeInTheDocument()
      expect(within(route).getByRole('button', { name: more })).toBeInTheDocument()
    },
  )

  it('links a duty with a drafting template to its draft', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    await openObligations()
    const [draft] = within(section(/^From 2 December 2027/)).getAllByRole('link', {
      name: 'Draft ready',
    })
    expect(draft).toHaveAttribute(
      'href',
      expect.stringContaining('/app/documents/art_26_2_oversight') as string,
    )
  })

  it('summarises a high-risk provider with a link to its duties', async () => {
    const benefits = toolRow('Benefits checker', legacyForPublicAuthorities())
    tools = [benefits]
    await openObligations()
    const from2030 = section('From 2 August 2030')
    expect(from2030).toHaveTextContent(
      '3 provider duties, from building and documenting the tool to monitoring it after launch.',
    )
    expect(within(from2030).queryAllByRole('checkbox')).toHaveLength(0)
    expect(
      within(from2030).getByRole('link', { name: 'Open the provider duties' }),
    ).toHaveAttribute('href', `/app/inventory/${String(benefits['id'])}`)
  })
})

describe('Obligations, what each section holds', () => {
  it.each([
    ['en', 'In force since 2 August 2026', 'Transparency, Art. 50'],
    ['de', 'In Kraft seit dem 2. August 2026', 'Transparenz, Art. 50'],
  ] as const)(
    '(%s) names the transparency duties beside their date',
    async (language, name, line) => {
      tools = [toolRow('Product photo generator', limitedRisk())]
      await openObligations('/app/obligations', language)
      expect(section(name)).toHaveAccessibleDescription(line)
    },
  )

  it('sets a dated section apart from the route section of the same date', async () => {
    const chat = limitedRisk()
    const [literacy] = chat.obligations ?? []
    if (!literacy) throw new Error('The fixture has duties.')
    const assessment = {
      ...literacy,
      key: 'art-6-4',
      article: 'art:6:4',
      applies_from: '2027-12-02',
    }
    tools = [
      toolRow('Applicant screening', decidedHighRisk()),
      toolRow('Customer chat assistant', {
        ...chat,
        obligations: [...(chat.obligations ?? []), assessment],
      }),
    ]
    await openObligations()
    // One "From 2 December 2027"; the other names what it holds in its title.
    const [route, ...others] = screen.getAllByRole('region', { name: /^From 2 December 2027/ })
    expect(others).toEqual([])
    expect(route).toHaveAccessibleDescription('High-risk, Annex III')
    const plain = section('Art. 6(4) from 2 December 2027')
    expect(plain).not.toHaveAccessibleDescription()
    expect(plain).toHaveTextContent('Customer chat assistant')
  })

  it.each([
    ['en', 'From 2 December 2027', 'Art. 6(4)'],
    ['de', 'Ab dem 2. Dezember 2027', 'Art. 6 Abs. 4'],
  ] as const)(
    '(%s) keeps the plain title of a dated section no route section shares, its article beside it',
    async (language, title, article) => {
      const chat = limitedRisk()
      const [literacy] = chat.obligations ?? []
      if (!literacy) throw new Error('The fixture has duties.')
      const assessment = {
        ...literacy,
        key: 'art-6-4',
        article: 'art:6:4',
        applies_from: '2027-12-02',
      }
      tools = [toolRow('Customer chat assistant', { ...chat, obligations: [assessment] })]
      await openObligations('/app/obligations', language)
      const lone = section(title)
      expect(lone).toHaveAccessibleDescription(article)
      expect(lone).toHaveTextContent('Customer chat assistant')
    },
  )

  it.each([
    ['en', 'Other duties from 2 December 2027', 'No specific duties'],
    ['de', 'Weitere Pflichten ab dem 2. Dezember 2027', 'Keine besonderen Pflichten'],
  ] as const)(
    '(%s) calls a same-date section of several articles "other duties"; By tool shows a tool without any',
    async (language, other, none) => {
      const chat = limitedRisk()
      const [literacy] = chat.obligations ?? []
      if (!literacy) throw new Error('The fixture has duties.')
      const later = { ...literacy, applies_from: '2027-12-02' }
      tools = [
        toolRow('Applicant screening', decidedHighRisk()),
        toolRow('Customer chat assistant', {
          ...chat,
          obligations: [
            { ...later, key: 'art-6-4', article: 'art:6:4' },
            { ...later, key: 'art-49-2', article: 'art:49:2' },
          ],
        }),
        toolRow('Invoice matching', outOfScope()),
      ]
      const { user } = await openObligations('/app/obligations', language)
      expect(section(other)).toHaveTextContent('Customer chat assistant')

      await user.click(
        screen.getByRole('button', { name: language === 'en' ? 'By tool' : 'Nach Tool' }),
      )
      const invoices = (await screen.findByRole('link', { name: 'Invoice matching' })).closest(
        '[data-tone]',
      )
      expect(invoices).toHaveTextContent(none)
    },
  )

  it.each([
    ['en', 'From 2 December 2026'],
    ['de', 'Ab dem 2. Dezember 2026'],
  ] as const)(
    '(%s) dates a Stop now duty that only applies from December 2026',
    async (language, from) => {
      const [literacy] = decidedHighRisk().obligations ?? []
      if (!literacy) throw new Error('The fixture has duties.')
      const banned = (key: string, article: string, appliesFrom: string, label: string) => ({
        ...literacy,
        key,
        article,
        applies_from: appliesFrom,
        label_en: label,
        label_de: label,
        applies_if: null,
      })
      tools = [
        toolRow('Image app', {
          ...prohibitedResult(),
          obligations: [
            banned('prohibited-emotions', 'art:5:1:f', '2025-02-02', 'Stop the emotion reading'),
            banned(
              'prohibited-intimate-images',
              'art:5:1:ba',
              '2026-12-02',
              'Stop the intimate images',
            ),
            banned('prohibited-child-images', 'art:5:1:bb', '2026-12-02', 'Stop the child images'),
          ],
        }),
      ]
      await openObligations('/app/obligations', language)
      const stop = section(language === 'en' ? 'Stop now' : 'Jetzt beenden')
      const [inForce, ba, bb] = within(stop).getAllByRole('listitem')
      expect(ba).toHaveTextContent(`Stop the intimate images${from}`)
      expect(bb).toHaveTextContent(`Stop the child images${from}`)
      // Banned since February 2025: no date to wait for.
      expect(inForce).not.toHaveTextContent(language === 'en' ? /From \d/ : /Ab dem \d/)
    },
  )
})

describe('Obligations, uncertain and legacy tools', () => {
  it.each([
    [
      'en',
      'These duties apply if the stricter reading holds. Klar recommends a legal review before you plan around it.',
      'These duties apply if the stricter reading holds. Answer the open question to find out whether they do.',
    ],
    [
      'de',
      'Diese Pflichten gelten, wenn die strengere Auslegung zutrifft. Klar empfiehlt eine rechtliche Prüfung, bevor Sie damit planen.',
      'Diese Pflichten gelten, wenn die strengere Auslegung zutrifft. Beantworten Sie die offene Frage, um zu klären, ob sie gelten.',
    ],
  ] as const)(
    '(%s) flags an ambiguous and a needs-info tool',
    async (language, ambiguous, info) => {
      tools = [
        toolRow('CV data extraction', ambiguousResult()),
        toolRow('Shift planner', WORKED_EXAMPLE),
      ]
      await openObligations('/app/obligations?group=tool', language)
      const cv = screen.getByRole('link', { name: 'CV data extraction' }).closest('[data-tone]')
      const shifts = screen.getByRole('link', { name: 'Shift planner' }).closest('[data-tone]')
      expect(cv).toHaveTextContent(ambiguous)
      expect(shifts).toHaveTextContent(info)
      expect(cv).toHaveTextContent(
        language === 'en' ? 'High-risk, assumed' : 'Hochrisiko, angenommen',
      )
    },
  )

  it.each([
    ['en', 'Only after a significant change', 'Art. 111(2)'],
    ['de', 'Nur nach einer erheblichen Änderung', 'Art. 111 Abs. 2'],
  ] as const)(
    '(%s) shows a legacy duty that waits for a significant change with its tag',
    async (language, heading, tag) => {
      tools = [toolRow('Old screener', legacyMarkedDeployer())]
      await openObligations('/app/obligations', language)
      const waiting = section(heading)
      expect(waiting).toHaveTextContent(tag)
      const [first] = within(waiting).getAllByRole('listitem')
      expect(first).toHaveTextContent(
        language === 'en'
          ? 'Only after a significant changeArt. 111(2)'
          : 'Nur nach einer erheblichen ÄnderungArt. 111 Abs. 2',
      )
    },
  )

  it('shows a legacy duty for public authorities from 2 August 2030 with its tag', async () => {
    const legacy = withRouteDuties(decidedHighRisk(), {
      applies_from: '2030-08-02',
      legacy: 'legacy_public_authority',
    })
    tools = [toolRow('Benefits screener', legacy)]
    await openObligations()
    const [first] = within(section('From 2 August 2030')).getAllByRole('listitem')
    expect(first).toHaveTextContent('From 2 August 2030Art. 111(2)')
  })
})

describe('Obligations, dates', () => {
  it('names the earliest date still ahead and the tools whose duties start then', async () => {
    tools = [
      toolRow('Product photo generator', limitedRisk()),
      toolRow('Applicant screening', decidedHighRisk()),
      toolRow('Shift planner', WORKED_EXAMPLE),
    ]
    await openObligations()
    expect(section('Next date')).toHaveTextContent(
      '2 December 2027In 14 monthsDuties start for Applicant screening, and possibly for 1 more tool.',
    )
  })

  it('swaps the route dates under the original text, with the notice', async () => {
    tools = [
      toolRow('Applicant screening', decidedHighRisk()),
      toolRow('Benefits checker', legacyForPublicAuthorities()),
    ]
    await openObligations('/app/obligations?law=original')
    const [heading] = screen.getAllByRole('heading', { name: /^From 2 December 2027/ })
    expect(heading?.querySelector('.law-amended-only')).toHaveTextContent('2 December 2027')
    expect(heading?.querySelector('.law-original-only')).toHaveTextContent('2 August 2026')
    const tag = heading?.parentElement?.querySelector('.law-original-only:not(h2 *)')
    expect(tag).toHaveTextContent('Already applies')
    expect(
      screen.getByText(
        "Dates follow the original Art. 113. The duties shown are the amended text's.",
      ),
    ).toHaveAttribute('role', 'note')
    // Annex III's original date has come: the next date is Art. 111(2)'s, the same under both.
    expect(section('Next date')).toHaveTextContent('2 August 2030')
  })
})

describe('Obligations, relief notes under a duty (P31, D6)', () => {
  const RELIEF = 'Keep it short for a small company (Art. 4).'
  const RELIEF_DE = 'Für ein kleines Unternehmen kurz halten (Art. 4).'

  /** A limited-risk tool whose first duty carries a relief note in both languages. */
  function relievedTool(): Record<string, unknown> {
    const chat = limitedRisk()
    const [first, ...rest] = chat.obligations ?? []
    if (!first) throw new Error('The fixture has duties.')
    const relieved = { ...first, relief_note: RELIEF, relief_note_de: RELIEF_DE }
    return toolRow('Customer chat assistant', { ...chat, obligations: [relieved, ...rest] })
  }

  it.each([
    ['sme', 'en', `Relief for your company: ${RELIEF}`],
    ['smc', 'de', `Erleichterung für Ihr Unternehmen: ${RELIEF_DE}`],
  ] as const)(
    'shows the relief under the duty for a company of size %s (%s)',
    async (size, language, line) => {
      sizeClass = size
      tools = [relievedTool()]
      await openObligations('/app/obligations', language)
      expect(await screen.findByText(line)).toBeInTheDocument()
    },
  )

  it.each([['none'], [null]] as const)('shows no relief for size class %s', async (size) => {
    sizeClass = size
    tools = [relievedTool()]
    await openObligations()
    await screen.findByText('Nordwerk Logistik GmbH')
    expect(screen.queryByText(/^Relief for your company: /)).toBeNull()
  })

  it('shows no relief under the original text', async () => {
    sizeClass = 'sme'
    tools = [relievedTool()]
    await openObligations('/app/obligations?law=original')
    await screen.findByText('Nordwerk Logistik GmbH')
    expect(screen.queryByText(/^Relief for your company: /)).toBeNull()
  })

  it('sends the size class with the checklist', async () => {
    sizeClass = 'smc'
    tools = [relievedTool()]
    const { user } = await openObligations()
    await screen.findByText('Nordwerk Logistik GmbH')
    await user.click(screen.getByRole('button', { name: 'Download Word' }))
    await vi.waitFor(() => expect(checklists).toHaveLength(1))
    expect(checklists[0]).toMatchObject({ size_class: 'smc' })
  })
})

describe('Obligations, the checklist download', () => {
  it('sends every duty with its ticked state and saves the Word file', async () => {
    const screening = toolRow('Applicant screening', decidedHighRisk())
    tools = [screening]
    ticks = [{ system_id: String(screening['id']), obligation_key: 'hr-deployer-logs' }]
    const { user } = await openObligations()
    await user.click(screen.getByRole('button', { name: 'Download Word' }))
    await vi.waitFor(() => expect(downloads).toEqual(['klar-obligations-checklist.docx']))
    const [sent] = checklists as {
      format: string
      company: string | null
      language: string
      tools: { name: string; duties: { article: string; is_done: boolean }[] }[]
    }[]
    expect(sent?.format).toBe('docx')
    expect(sent?.language).toBe('en')
    expect(sent?.company).toBe('Nordwerk Logistik GmbH')
    const duties = sent?.tools[0]?.duties ?? []
    expect(duties).toHaveLength(11)
    expect(duties.filter((duty) => duty.is_done).map((duty) => duty.article)).toEqual(['art:26:6'])
  })

  it('asks for the PDF in the screen language', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    const { user } = await openObligations('/app/obligations', 'de')
    await user.click(screen.getByRole('button', { name: 'PDF herunterladen' }))
    await vi.waitFor(() => expect(checklists).toHaveLength(1))
    expect(checklists[0]).toMatchObject({ format: 'pdf', language: 'de', law_version: 'amended' })
  })

  it('asks for the checklist under the original text when the screen shows it', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    const { user } = await openObligations('/app/obligations?law=original')
    await user.click(screen.getByRole('button', { name: 'Download PDF' }))
    await vi.waitFor(() => expect(checklists).toHaveLength(1))
    expect(checklists[0]).toMatchObject({ format: 'pdf', law_version: 'original' })
  })

  it('counts a result stored before duties had keys the same on screen and in the checklist', async () => {
    const stored = decidedHighRisk()
    const keyless = {
      ...stored,
      // As stored before P24: the duty has no key at all (the JSON drops undefined).
      obligations: (stored.obligations ?? []).map((duty) => ({ ...duty, key: undefined })),
    }
    tools = [toolRow('Applicant screening', keyless)]
    const { user } = await openObligations()
    // Nothing to tick: no box, and nothing counted.
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
    expect(progressLine()).toBe('0 of 0 done')
    await user.click(screen.getByRole('button', { name: 'Download PDF' }))
    await vi.waitFor(() => expect(checklists).toHaveLength(1))
    const [sent] = checklists as { tools: { duties: { is_done: boolean | null }[] }[] }[]
    const states = sent?.tools[0]?.duties.map((duty) => duty.is_done) ?? []
    // Sent without a state, so the checklist lists them uncounted too: 0 of 0 done.
    expect(states).toHaveLength(11)
    expect(new Set(states)).toEqual(new Set([null]))
  })
})

describe('Obligations, German and accessibility', () => {
  it('reads in German', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    await openObligations('/app/obligations', 'de')
    expect(
      screen.getByText(
        'Alle Pflichten Ihres 1 eingestuften Tools, nach dem Datum, ab dem sie gelten.',
      ),
    ).toBeInTheDocument()
    expect(section('Fortschritt')).toHaveTextContent(
      '0 von 11 erledigtHaken Sie Pflichten ab, sobald sie erledigt sind. Klar führt die Liste; ob die Arbeit getan ist, prüft Klar nicht.',
    )
    expect(section('Nächstes Datum')).toHaveTextContent(
      '2. Dezember 2027In 14 MonatenPflichten beginnen für Applicant screening.',
    )
    expect(section('Checkliste mitnehmen')).toHaveTextContent(
      'Jede Pflicht mit Artikel und Datum, für Ihre Unterlagen oder Ihre rechtliche Beratung.',
    )
    expect(screen.getByRole('button', { name: 'Word herunterladen' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Gruppieren nach' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nach Datum' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Nach Tool' })).toBeInTheDocument()
    expect(
      screen.getByText('Klar führt die Liste; ob die Arbeit getan ist, prüft Klar nicht.'),
    ).toBeInTheDocument()
  })

  it('names the sections, cards and links in German', async () => {
    tools = [
      toolRow('Applicant screening', decidedHighRisk()),
      toolRow('Call mood scoring', prohibitedResult()),
      toolRow('Benefits checker', legacyForPublicAuthorities()),
      toolRow('Route optimisation', minimalRisk()),
    ]
    await openObligations('/app/obligations', 'de')
    expect(section('Jetzt beenden')).toHaveTextContent(
      'Jetzt beendenVerbotenVerbotene Praktiken, Art. 5',
    )
    expect(section('Jetzt beenden')).toHaveTextContent(
      'Nutzen oder liefern Sie es ab sofort nicht mehr',
    )
    expect(section('In Kraft seit dem 2. Februar 2025')).toHaveTextContent('In Kraft')
    const route = section(/^Ab dem 2\. Dezember 2027/)
    expect(route).toHaveTextContent('In 14 Monaten')
    expect(route).toHaveTextContent('Hochrisiko, Anhang III')
    expect(within(route).getByText('0 von 10 erledigt')).toBeInTheDocument()
    expect(
      within(route).getByRole('button', { name: 'Alle 10 Pflichten zeigen' }),
    ).toBeInTheDocument()
    expect(within(route).getAllByRole('link', { name: 'Entwurf bereit' }).length).toBeGreaterThan(0)
    const from2030 = section(/^Ab dem 2\. August 2030/)
    expect(from2030).toHaveTextContent(
      '3 Anbieterpflichten, vom Entwickeln und Dokumentieren des Tools bis zur Beobachtung nach dem Inverkehrbringen.',
    )
    expect(
      within(from2030).getByRole('link', { name: 'Anbieterpflichten öffnen' }),
    ).toBeInTheDocument()
    expect(section('Keine besonderen Pflichten')).toHaveTextContent(
      'Minimales Risiko oder außerhalb des Anwendungsbereichs',
    )
  })

  it('says in German when a tick is not saved, and when there is nothing to list', async () => {
    server.use(...dutyProgressHandlers(true))
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    const { user, unmount } = await openObligations('/app/obligations', 'de')
    await user.click(
      screen.getByRole('checkbox', {
        name: 'Das Tool gemäß der Betriebsanleitung des Anbieters einsetzen',
      }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Klar konnte diesen Haken nicht speichern. Bitte versuchen Sie es erneut.',
    )
    unmount()
    tools = []
    renderRoute('/app/obligations')
    expect(await screen.findByText('Noch keine Pflichten')).toBeInTheDocument()
    expect(
      screen.getByText('Stufen Sie ein Tool ein, um zu sehen, was es von Ihnen verlangt.'),
    ).toBeInTheDocument()
  })

  it('has no axe violations', async () => {
    tools = [
      toolRow('Applicant screening', decidedHighRisk()),
      toolRow('Call mood scoring', prohibitedResult()),
      toolRow('CV data extraction', ambiguousResult()),
      toolRow('Route optimisation', minimalRisk()),
    ]
    const { container } = await openObligations()
    // jsdom can't compute colours over the glass: contrast is checked in the browser project.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })

  it('invites a first classification while no tool has a result', async () => {
    tools = [toolRow('Draft tool', null)]
    await i18n.changeLanguage('en')
    renderRoute('/app/obligations')
    expect(await screen.findByText('No duties yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Classify your first tool' })).toBeInTheDocument()
  })
})
