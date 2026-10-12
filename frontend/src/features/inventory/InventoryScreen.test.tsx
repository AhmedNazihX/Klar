import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import { clearDraft } from '@/features/classify/classification-store'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  classifyHandler,
  decidedHighRisk,
  legacyForPublicAuthorities,
  legacyMarkedDeployer,
  limitedRisk,
  minimalRisk,
  outOfScope,
  WORKED_EXAMPLE,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import {
  ambiguousResult,
  INVENTORY_TOOLS_URL,
  prohibitedResult,
  SAVE_TOOL_URL,
  savedRunHandler,
  toolRow,
} from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import {
  prohibitedHandlers,
  RECORDED_PROHIBITED,
  type ProhibitedTraffic,
} from '@/test/prohibited-fixtures'
import { renderRoute } from '@/test/test-utils'
import { IMPORT_URL, userDataHandlers } from '@/test/user-data-handlers'

// The app's Supabase client, pointed at the MSW network boundary.
vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

/** What a checked tool does, as its prohibited-practices check states it (the fixtures share it). */
const WHAT = 'The tool reads job applications, scores them, and shows HR a ranked shortlist.'

/** A day after Art. 50 started to apply (2 Aug 2026) and before the amended Annex III date. */
const TODAY = new Date(2026, 9, 7, 12)

let tools: Record<string, unknown>[] = []

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(TODAY)
  clearDraft()
  tools = []
  server.use(
    ...userDataHandlers(
      () => [],
      () => tools.length,
      () => tools,
    ),
  )
})
afterEach(() => {
  vi.useRealTimers()
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

/** An inventory like the artboard's: one tool of every kind the screen tells apart. */
function artboardTools(): Record<string, unknown>[] {
  return [
    toolRow('Applicant screening', decidedHighRisk(), {
      description: 'Scores and ranks job applications for HR\nBought from a vendor.',
    }),
    toolRow('Call mood scoring', prohibitedResult()),
    toolRow('Shift planner', WORKED_EXAMPLE),
    toolRow('CV data extraction', ambiguousResult()),
    toolRow('Product photo generator', limitedRisk()),
    toolRow('Route optimisation', minimalRisk()),
    toolRow('Invoice matching', outOfScope()),
    toolRow('Old screener', legacyMarkedDeployer()),
    toolRow('Benefits checker', legacyForPublicAuthorities()),
    toolRow('Draft tool', null),
    toolRow('Edited file', { risk_class: 'harmless' }),
  ]
}

async function openInventory(language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute('/app/inventory')
  await screen.findByRole('heading', { level: 1 })
  return { user, ...rendered }
}

/** The table's body rows, each as its cells' text. */
async function tableRows(name: string): Promise<string[][]> {
  const table = await screen.findByRole('table', { name })
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) =>
      within(row)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    )
}

describe('Inventory, the company summary', () => {
  it('says what comes first, what is in force and the tools per class, flagging assumed ones', async () => {
    tools = artboardTools()
    await openInventory()
    const summary = await screen.findByRole('region', { name: 'Company summary' })

    expect(summary).toHaveTextContent(
      'Call mood scoring is prohibited: stop using it now. Next come your duties as the deployer of Applicant screening, from 2 December 2027',
    )
    expect(within(summary).getByText('Already in force')).toBeInTheDocument()
    expect(within(summary).getByText('Transparency, 1 tool')).toBeInTheDocument()
    expect(within(summary).getByText('Art. 50, since 2 Aug 2026')).toBeInTheDocument()
    const counts = within(summary).getByRole('list', { name: 'Tools per class' })
    expect(
      within(counts)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      '1 Prohibited',
      '5 High-risk(2 assumed)',
      '1 Limited risk',
      '1 Minimal risk',
      '1 Out of scope',
    ])
    expect(summary).toHaveTextContent(
      '2 tools are counted in their stricter class until their open questions are settled.',
    )
    // The rows are what the browser stored (P3): never presented as a verified record.
    expect(summary).toHaveTextContent(
      "Summed up from the results saved in your data. Klar doesn't re-check saved results, so read this as guidance, not a verified record.",
    )
    expect(screen.getByText('11 tools in your inventory.', { selector: 'p' })).toBeInTheDocument()
  })

  it('says so when nothing is prohibited and no duty is still to start', async () => {
    tools = [toolRow('Route optimisation', minimalRisk())]
    await openInventory()
    const summary = await screen.findByRole('region', { name: 'Company summary' })
    expect(summary).toHaveTextContent('No tool is prohibited, and no duties are still to start.')
    expect(within(summary).queryByText('Already in force')).toBeNull()
    expect(screen.queryByRole('region', { name: /need you/ })).toBeNull()
    expect(
      screen.getByText('1 tool, classified under the AI Act as amended on 27 July 2026.'),
    ).toBeInTheDocument()
  })

  it('reads the same in German', async () => {
    tools = artboardTools()
    await openInventory('de')
    const summary = await screen.findByRole('region', { name: 'Unternehmensübersicht' })
    expect(summary).toHaveTextContent(
      'Call mood scoring ist verboten: Nutzen Sie es ab sofort nicht mehr. Als Nächstes kommen Ihre Pflichten als Betreiber von Applicant screening, ab dem 2. Dezember 2027',
    )
    expect(within(summary).getByText('Bereits in Kraft')).toBeInTheDocument()
    expect(within(summary).getByText('Transparenz, 1 Tool')).toBeInTheDocument()
    expect(within(summary).getByText('Art. 50, seit dem 2. Aug. 2026')).toBeInTheDocument()
    const counts = within(summary).getByRole('list', { name: 'Tools je Klasse' })
    expect(within(counts).getAllByRole('listitem')[1]).toHaveTextContent(
      '5 Hochrisiko(2 angenommen)',
    )
    expect(summary).toHaveTextContent(
      '2 Tools werden in ihrer strengeren Klasse gezählt, bis ihre offenen Fragen geklärt sind.',
    )
    expect(summary).toHaveTextContent(
      'Zusammengefasst aus den in Ihren Daten gespeicherten Ergebnissen. Klar prüft gespeicherte Ergebnisse nicht erneut; lesen Sie dies als Orientierung, nicht als geprüften Nachweis.',
    )
  })
})

describe('Inventory, the summary sentence', () => {
  async function summaryUnder(path: string, language: 'en' | 'de'): Promise<HTMLElement> {
    await i18n.changeLanguage(language)
    renderRoute(path)
    const name = language === 'de' ? 'Unternehmensübersicht' : 'Company summary'
    return screen.findByRole('region', { name })
  }

  it.each([
    [
      'en',
      'deployer',
      'Your duties as the deployer of Applicant screening have applied since 2 August 2026.',
    ],
    [
      'de',
      'deployer',
      'Ihre Pflichten als Betreiber von Applicant screening gelten seit dem 2. August 2026.',
    ],
    [
      'en',
      'provider',
      'Your duties as the provider of Applicant screening have applied since 2 August 2026.',
    ],
    [
      'de',
      'provider',
      'Ihre Pflichten als Anbieter von Applicant screening gelten seit dem 2. August 2026.',
    ],
    [
      'en',
      'importer',
      'Your duties as the importer of Applicant screening have applied since 2 August 2026.',
    ],
    [
      'de',
      'importer',
      'Ihre Pflichten als Einführer von Applicant screening gelten seit dem 2. August 2026.',
    ],
    [
      'en',
      'distributor',
      'Your duties as the distributor of Applicant screening have applied since 2 August 2026.',
    ],
    [
      'de',
      'distributor',
      'Ihre Pflichten als Händler von Applicant screening gelten seit dem 2. August 2026.',
    ],
    ['en', null, 'The duties for Applicant screening have applied since 2 August 2026.'],
    ['de', null, 'Die Pflichten für Applicant screening gelten seit dem 2. August 2026.'],
  ] as const)(
    'says the route duties already apply under the original text once their date has come (%s, %s)',
    async (language, role, sentence) => {
      tools = [toolRow('Applicant screening', { ...decidedHighRisk(), role })]
      expect(await summaryUnder('/app/inventory?law=original', language)).toHaveTextContent(
        sentence,
      )
    },
  )

  it.each([
    ['en', 'Next come your duties as the deployer of Applicant screening, from 2 August 2026.'],
    [
      'de',
      'Als Nächstes kommen Ihre Pflichten als Betreiber von Applicant screening, ab dem 2. August 2026.',
    ],
  ] as const)(
    'names the original route date as still ahead the day before (%s)',
    async (language, sentence) => {
      vi.setSystemTime(new Date(2026, 7, 1, 12))
      tools = [toolRow('Applicant screening', decidedHighRisk())]
      expect(await summaryUnder('/app/inventory?law=original', language)).toHaveTextContent(
        sentence,
      )
    },
  )

  it.each([
    [
      'en',
      'Next come your duties as the deployer of Shift planner, from 2 December 2027. Its class (High-risk) is assumed until its open question is settled.',
    ],
    [
      'de',
      'Als Nächstes kommen Ihre Pflichten als Betreiber von Shift planner, ab dem 2. Dezember 2027. Seine Klasse (Hochrisiko) ist angenommen, bis seine offene Frage geklärt ist.',
    ],
  ] as const)(
    'says the class is assumed when only an assumed result has dated duties (%s)',
    async (language, sentence) => {
      tools = [
        toolRow('Shift planner', WORKED_EXAMPLE),
        toolRow('Route optimisation', minimalRisk()),
      ]
      expect(await summaryUnder('/app/inventory', language)).toHaveTextContent(sentence)
    },
  )

  it('names a decided result before an assumed one', async () => {
    tools = [
      toolRow('Shift planner', WORKED_EXAMPLE),
      toolRow('Applicant screening', decidedHighRisk()),
    ]
    const summary = await summaryUnder('/app/inventory', 'en')
    expect(summary).toHaveTextContent(
      'Next come your duties as the deployer of Applicant screening, from 2 December 2027.',
    )
    expect(summary).not.toHaveTextContent('is assumed until')
  })

  it.each([
    [
      'en',
      'Call mood scoring is prohibited: stop using it now. Its class (Prohibited) is assumed until its open question is settled.',
    ],
    [
      'de',
      'Call mood scoring ist verboten: Nutzen Sie es ab sofort nicht mehr. Seine Klasse (Verboten) ist angenommen, bis seine offene Frage geklärt ist.',
    ],
  ] as const)(
    'says a prohibited class is assumed while its question is open (%s)',
    async (language, sentence) => {
      tools = [toolRow('Call mood scoring', { ...prohibitedResult(), status: 'legally_ambiguous' })]
      expect(await summaryUnder('/app/inventory', language)).toHaveTextContent(sentence)
    },
  )

  it.each([
    [
      'en',
      '2 tools are prohibited: stop using them now. One of them is assumed prohibited until its open question is settled.',
    ],
    [
      'de',
      '2 Tools sind verboten: Nutzen Sie sie ab sofort nicht mehr. Bei einem davon ist das Verbot angenommen, bis seine offene Frage geklärt ist.',
    ],
  ] as const)('says how many prohibited tools are assumed (%s)', async (language, sentence) => {
    tools = [
      toolRow('Call mood scoring', { ...prohibitedResult(), status: 'needs_more_information' }),
      toolRow('Emotion reader', prohibitedResult()),
    ]
    expect(await summaryUnder('/app/inventory', language)).toHaveTextContent(sentence)
  })

  it.each([
    [
      'en',
      '3 tools are prohibited: stop using them now. 2 of them are assumed prohibited until their open questions are settled.',
    ],
    [
      'de',
      '3 Tools sind verboten: Nutzen Sie sie ab sofort nicht mehr. Bei 2 davon ist das Verbot angenommen, bis ihre offenen Fragen geklärt sind.',
    ],
  ] as const)('counts several assumed prohibited tools (%s)', async (language, sentence) => {
    tools = [
      toolRow('Call mood scoring', { ...prohibitedResult(), status: 'needs_more_information' }),
      toolRow('Face scraper', { ...prohibitedResult(), status: 'legally_ambiguous' }),
      toolRow('Emotion reader', prohibitedResult()),
    ]
    expect(await summaryUnder('/app/inventory', language)).toHaveTextContent(sentence)
  })

  it('says nothing is assumed when the prohibited tool is decided', async () => {
    tools = [toolRow('Call mood scoring', prohibitedResult())]
    const summary = await summaryUnder('/app/inventory', 'en')
    expect(summary).toHaveTextContent('Call mood scoring is prohibited: stop using it now.')
    expect(summary).not.toHaveTextContent('assumed')
  })

  it.each([
    ['en', 'Your tool is prohibited: stop using it now.'],
    ['de', 'Ihr Tool ist verboten: Nutzen Sie es ab sofort nicht mehr.'],
  ] as const)('names an unnamed tool in the reader’s language (%s)', async (language, sentence) => {
    tools = [toolRow('ignored', prohibitedResult(), { name: null })]
    expect(await summaryUnder('/app/inventory', language)).toHaveTextContent(sentence)
    const table = await screen.findByRole('table')
    expect(
      within(table).getByRole('link', { name: language === 'de' ? 'Ihr Tool' : 'Your tool' }),
    ).toBeInTheDocument()
  })
})

describe('Inventory, the tools that need you', () => {
  it('lists the prohibited, paused and ambiguous tools with what to do, each opening its result', async () => {
    tools = artboardTools()
    await openInventory()
    const panel = await screen.findByRole('region', { name: '3 tools need you' })
    const links = within(panel).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual([
      'Call mood scoringProhibitedStop using or supplying it now',
      'Shift plannerNeeds more informationAnswer 1 question to finish the check',
      'CV data extractionLegally ambiguousTwo readings of Art. 6(3). Legal review recommended',
    ])
    expect(links[0]).toHaveAttribute('href', `/app/inventory/${String(tools[1]?.['id'])}`)
  })

  it('reads the same in German', async () => {
    tools = artboardTools()
    await openInventory('de')
    const panel = await screen.findByRole('region', { name: '3 Tools brauchen Sie' })
    expect(
      within(panel)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual([
      'Call mood scoringVerbotenNutzen oder liefern Sie es ab sofort nicht mehr',
      'Shift plannerWeitere Angaben nötigBeantworten Sie 1 Frage, um die Prüfung abzuschließen',
      'CV data extractionRechtlich unklarZwei Lesarten von Art. 6 Abs. 3. Rechtliche Prüfung empfohlen',
    ])
  })
})

describe('Inventory, the table', () => {
  it('shows every tool, strictest class first, with role, class, basis, date and status', async () => {
    tools = artboardTools()
    await openInventory()
    expect(await tableRows('Your tools and their results')).toEqual([
      [`Call mood scoring${WHAT}`, 'Deployer', 'Prohibited', 'Art. 5(1)(f)', '–', 'Decided'],
      [
        `Applicant screening${WHAT}`,
        'Deployer',
        'High-risk',
        'Annex III 4(a)',
        '2 Dec 20272 Aug 2026',
        'Decided',
      ],
      [
        `Shift planner${WHAT}`,
        'Deployer',
        'High-risk, assumed',
        'Annex III 4(a)',
        '2 Dec 20272 Aug 2026',
        'Needs more information',
      ],
      [
        `CV data extraction${WHAT}`,
        'Deployer',
        'High-risk, assumed',
        'Annex III 4(a), Art. 6(3)',
        '2 Dec 20272 Aug 2026',
        'Legally ambiguous',
      ],
      [
        `Old screener${WHAT}`,
        'Deployer',
        'High-risk',
        'Annex III 4(a)',
        'Only after a significant changeArt. 111(2)',
        'Decided',
      ],
      [
        `Benefits checker${WHAT}`,
        'Provider',
        'High-risk',
        'Annex III 4(a)',
        'From 2 Aug 2030Art. 111(2)',
        'Decided',
      ],
      [
        `Product photo generator${WHAT}`,
        'Deployer',
        'Limited risk',
        'Art. 50(4)',
        'Since 2 Aug 2026',
        'Decided',
      ],
      [`Route optimisation${WHAT}`, 'Deployer', 'Minimal risk', 'No specific duty', '–', 'Decided'],
      [
        // Out of scope: the checks stopped before the practices, so the description says it.
        'Invoice matchingInvoice matching: what it does.',
        '–',
        'Out of scope',
        'Art. 3(1)',
        '–',
        'Decided',
      ],
      ['Draft toolDraft tool: what it does.', '–', '–', '–', '–', 'Not checked yet'],
      ['Edited fileEdited file: what it does.', '–', '–', '–', '–', "Saved result can't be read"],
    ])
  })

  it('shows the route dates under the switch: the amended one by default, the original one under it', async () => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    await openInventory()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('2 Dec 2027')).toHaveClass('law-amended-only')
    expect(within(table).getByText('2 Aug 2026')).toHaveClass('law-original-only')
  })

  it('reads the same in German', async () => {
    tools = artboardTools()
    await openInventory('de')
    const rows = await tableRows('Ihre Tools und ihre Ergebnisse')
    expect(rows[2]).toEqual([
      `Shift planner${WHAT}`,
      'Betreiber',
      'Hochrisiko, angenommen',
      'Anhang III Nr. 4 Buchst. a',
      '2. Dez. 20272. Aug. 2026',
      'Weitere Angaben nötig',
    ])
    expect(rows[4]?.[4]).toBe('Nur nach einer erheblichen ÄnderungArt. 111 Abs. 2')
    expect(rows[5]?.[4]).toBe('Ab dem 2. Aug. 2030Art. 111 Abs. 2')
    expect(rows[6]?.slice(3)).toEqual(['Art. 50 Abs. 4', 'Seit dem 2. Aug. 2026', 'Festgestellt'])
    expect(rows[7]?.[3]).toBe('Keine besondere Pflicht')
    expect(rows[9]?.[5]).toBe('Noch nicht geprüft')
    expect(rows[10]?.[5]).toBe('Gespeichertes Ergebnis nicht lesbar')
    expect(screen.getByRole('columnheader', { name: 'Gilt ab' })).toBeInTheDocument()
  })

  it("opens a tool's own result, read from the inventory", async () => {
    tools = artboardTools()
    const { user, router } = await openInventory()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByRole('link', { name: 'Applicant screening' }))

    expect(router.state.location.pathname).toBe(`/app/inventory/${String(tools[0]?.['id'])}`)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Applicant screening' }),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('region', { name: 'Result' })).getByText('High-risk'),
    ).toBeVisible()
  })

  it.each([
    [
      'en',
      'Result',
      "This tool isn't in your inventory. It may have been deleted, or it was checked in another browser.",
    ],
    [
      'de',
      'Ergebnis',
      'Dieses Tool ist nicht in Ihrem Inventar. Vielleicht wurde es gelöscht oder in einem anderen Browser geprüft.',
    ],
  ] as const)('says when a tool is not in the inventory (%s)', async (language, title, body) => {
    tools = [toolRow('Applicant screening', decidedHighRisk())]
    await i18n.changeLanguage(language)
    renderRoute('/app/inventory/0d6c1c55-1d2e-4f00-9a3b-6b3c3f1a2b99')
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.getByText(body)).toBeVisible()
  })

  it('passes axe', async () => {
    tools = artboardTools()
    const { container } = await openInventory()
    await screen.findByRole('table')
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe("A tool's result page, read from the inventory", () => {
  async function openTool(row: Record<string, unknown>, language: 'en' | 'de') {
    tools = [row]
    await i18n.changeLanguage(language)
    const user = userEvent.setup()
    const rendered = renderRoute(`/app/inventory/${String(row['id'])}`)
    await screen.findByRole('heading', { level: 1 })
    return { user, ...rendered }
  }

  it.each([
    [
      'en',
      'No saved result for this tool yet. Classify it to see its class and duties.',
      'Classify this tool',
    ],
    [
      'de',
      'Für dieses Tool gibt es noch kein gespeichertes Ergebnis. Stufen Sie es ein, um seine Klasse und Pflichten zu sehen.',
      'Dieses Tool einstufen',
    ],
  ] as const)(
    'says a tool has no saved result yet and offers to classify it (%s)',
    async (language, body, action) => {
      const row = toolRow('Draft tool', null)
      const { user, router } = await openTool(row, language)
      expect(screen.getByRole('heading', { level: 1, name: 'Draft tool' })).toBeInTheDocument()
      expect(screen.getByText(body)).toBeVisible()
      expect(screen.queryByText(/isn't in your inventory|nicht in Ihrem Inventar/)).toBeNull()

      await user.click(screen.getByRole('button', { name: action }))
      expect(router.state.location.pathname).toBe('/app/classify')
      // The tool's own words are in the form; nothing runs until the user starts the checks.
      expect(await screen.findByDisplayValue('Draft tool')).toBeInTheDocument()
      expect(
        screen.getByDisplayValue('Draft tool: what it does. More detail on a second line.'),
      ).toBeInTheDocument()
    },
  )

  it('reads a tool without a result once', async () => {
    let reads = 0
    server.use(
      http.get(INVENTORY_TOOLS_URL, ({ request }) => {
        if (new URL(request.url).searchParams.has('id')) reads += 1
        // Falls through to the rows' handler.
        return undefined
      }),
    )
    await openTool(toolRow('Draft tool', null), 'en')
    expect(screen.getByRole('button', { name: 'Classify this tool' })).toBeVisible()
    expect(reads).toBe(1)
  })

  it('saves "Classify this tool" on the same tool: its row shows the result, and no second row', async () => {
    const saves: Record<string, unknown>[] = []
    let classifyRequests = 0
    server.use(
      classifyHandler(WORKED_EXAMPLE_EVENTS, () => {
        classifyRequests += 1
      }),
      savedRunHandler(),
      // As the database does it: the run lands on the tool it names, as that tool's next run.
      http.post(SAVE_TOOL_URL, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        saves.push(body)
        tools = tools.map((tool) =>
          tool['id'] === body['target_system_id']
            ? { ...tool, run_no: 1, result: body['tool_result'] }
            : tool,
        )
        return HttpResponse.json(String(body['target_system_id']))
      }),
    )
    const row = toolRow('Draft tool', null)
    const id = String(row['id'])
    const { user, router } = await openTool(row, 'en')
    await user.click(screen.getByRole('button', { name: 'Classify this tool' }))
    await user.click(await screen.findByRole('button', { name: 'Run the checks' }))

    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${id}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Draft tool' })).toBeInTheDocument()
    expect(
      within(screen.getByRole('region', { name: 'Result' })).getByText(/High-risk/),
    ).toBeVisible()
    expect(saves).toEqual([
      expect.objectContaining({ target_system_id: id, tool_name: 'Draft tool' }),
    ])
    expect(classifyRequests).toBe(1)

    await router.navigate({ to: '/app/inventory' })
    const rows = await tableRows('Your tools and their results')
    expect(rows).toHaveLength(1)
    expect(rows[0]?.[0]).toMatch(/^Draft tool/)
    expect(rows[0]?.slice(2)).toEqual([
      'High-risk, assumed',
      'Annex III 4(a)',
      '2 Dec 20272 Aug 2026',
      'Needs more information',
    ])
    expect(classifyRequests).toBe(1)
  })

  it.each([
    [
      'en',
      "This saved result can't be read. The file it came from may have been edited. Classify the tool again to get a new result.",
    ],
    [
      'de',
      'Dieses gespeicherte Ergebnis ist nicht lesbar. Die Datei, aus der es stammt, wurde vielleicht bearbeitet. Stufen Sie das Tool erneut ein, um ein neues Ergebnis zu erhalten.',
    ],
  ] as const)('says a saved result cannot be read (%s)', async (language, body) => {
    await openTool(toolRow('Edited file', { ...decidedHighRisk(), status: 'approved' }), language)
    expect(screen.getByRole('heading', { level: 1, name: 'Edited file' })).toBeInTheDocument()
    expect(screen.getByText(body)).toBeVisible()
  })

  it.each([
    [
      'en',
      "Saved result. Klar doesn't re-check saved results, so read it as guidance, not a verified record.",
      'This is guidance, not legal advice. It is based only on the description provided and the version of the AI Act shown. Have decisions with legal consequences reviewed by a lawyer.',
    ],
    [
      'de',
      'Gespeichertes Ergebnis. Klar prüft gespeicherte Ergebnisse nicht erneut; lesen Sie es als Orientierung, nicht als geprüften Nachweis.',
      'Dies ist eine Orientierungshilfe, keine Rechtsberatung. Sie beruht ausschließlich auf der angegebenen Beschreibung und der angezeigten Fassung der KI-Verordnung. Lassen Sie Entscheidungen mit rechtlicher Tragweite anwaltlich prüfen.',
    ],
  ] as const)(
    "shows the app's own notice on a saved result, never the stored one (%s)",
    async (language, saved, disclaimer) => {
      const forged = { ...decidedHighRisk(), disclaimer: 'Certified compliant by Klar.' }
      await openTool(toolRow('Applicant screening', forged), language)
      expect(screen.getByText(saved)).toBeVisible()
      expect(screen.getByText(disclaimer, { exact: false })).toBeVisible()
      expect(screen.queryByText(/Certified compliant/)).toBeNull()
    },
  )

  it('shows a saved decided ban in the prohibited layout', async () => {
    server.use(...prohibitedHandlers({ lookups: [], letterBodies: [] }))
    await openTool(toolRow('Call mood scoring', RECORDED_PROHIBITED), 'en')
    expect(screen.getByRole('region', { name: 'What to do now' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Draft a message' })).toBeVisible()
    await screen.findByText('Art. 99(6), English')
  })

  it.each<[string, Partial<ClassificationResult>]>([
    ['refused (decision 030)', { risk_class: null, not_assessed: ['prohibited'] }],
    ['stored before decision 030 with a check not assessed', { not_assessed: ['transparency'] }],
  ])('never shows the prohibited layout for a saved ban %s', async (_, change) => {
    const traffic: ProhibitedTraffic = { lookups: [], letterBodies: [] }
    server.use(...prohibitedHandlers(traffic))
    await openTool(toolRow('Call mood scoring', { ...RECORDED_PROHIBITED, ...change }), 'en')
    expect(screen.getByRole('button', { name: 'Classify this tool' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'What to do now' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Why the checks stopped' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Draft a message' })).toBeNull()
    expect(traffic.lookups).toEqual([])
  })
})

describe('Inventory, adding tools', () => {
  it('starts empty, with Add a tool, Classify your first tool and Import your data', async () => {
    await openInventory()
    expect(await screen.findByText('No tools yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add a tool' })).toHaveAttribute(
      'href',
      '/app/classify',
    )
    expect(screen.getByRole('link', { name: 'Classify your first tool' })).toHaveAttribute(
      'href',
      '/app/classify',
    )
    expect(screen.getByLabelText('Import your data')).toBeInTheDocument()
    // A ghost button in the header's button row: Welcome's two-line hint stays off it.
    expect(
      screen.queryByText(
        'Restores a file you exported from Your data. Nothing is classified again.',
      ),
    ).toBeNull()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('shows the restored tools after an import, without classifying anything', async () => {
    server.use(
      http.post(IMPORT_URL, () => {
        tools = [toolRow('CV screener', decidedHighRisk())]
        return HttpResponse.json({ inventories: 1, systems: 1, classifications: 1 })
      }),
    )
    const { user } = await openInventory()
    await screen.findByText('No tools yet')
    const file = new File(['{"format":"aiact-user-data","version":1,"inventories":[]}'], 'x.json', {
      type: 'application/json',
    })
    await user.upload(screen.getByLabelText('Import your data'), file)

    const table = await screen.findByRole('table')
    expect(within(table).getByRole('link', { name: 'CV screener' })).toBeInTheDocument()
  })

  it('shows the error view when the tools cannot be read', async () => {
    server.use(
      http.get(INVENTORY_TOOLS_URL, () =>
        HttpResponse.json({ code: 'XX000', message: 'boom' }, { status: 500 }),
      ),
    )
    await openInventory()
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
  })
})
