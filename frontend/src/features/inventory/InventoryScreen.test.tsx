import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

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
import {
  ambiguousResult,
  INVENTORY_TOOLS_URL,
  prohibitedResult,
  toolRow,
} from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS, IMPORT_URL, userDataHandlers } from '@/test/user-data-handlers'

// The app's Supabase client, pointed at the MSW network boundary.
vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

/** A day after Art. 50 started to apply (2 Aug 2026) and before the amended Annex III date. */
const TODAY = new Date(2026, 9, 7, 12)

let tools: Record<string, unknown>[] = []

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(TODAY)
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
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
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
      [
        'Call mood scoringCall mood scoring: what it does.',
        'Deployer',
        'Prohibited',
        'Art. 5(1)(f)',
        '–',
        'Decided',
      ],
      [
        'Applicant screeningScores and ranks job applications for HR',
        'Deployer',
        'High-risk',
        'Annex III 4(a)',
        '2 Dec 20272 Aug 2026',
        'Decided',
      ],
      [
        'Shift plannerShift planner: what it does.',
        'Deployer',
        'High-risk, assumed',
        'Annex III 4(a)',
        '2 Dec 20272 Aug 2026',
        'Needs more information',
      ],
      [
        'CV data extractionCV data extraction: what it does.',
        'Deployer',
        'High-risk, assumed',
        'Annex III 4(a), Art. 6(3)',
        '2 Dec 20272 Aug 2026',
        'Legally ambiguous',
      ],
      [
        'Old screenerOld screener: what it does.',
        'Deployer',
        'High-risk',
        'Annex III 4(a)',
        'Only after a significant changeArt. 111(2)',
        'Decided',
      ],
      [
        'Benefits checkerBenefits checker: what it does.',
        'Provider',
        'High-risk',
        'Annex III 4(a)',
        'From 2 Aug 2030Art. 111(2)',
        'Decided',
      ],
      [
        'Product photo generatorProduct photo generator: what it does.',
        'Deployer',
        'Limited risk',
        'Art. 50(4)',
        'Since 2 Aug 2026',
        'Decided',
      ],
      [
        'Route optimisationRoute optimisation: what it does.',
        'Deployer',
        'Minimal risk',
        'No specific duty',
        '–',
        'Decided',
      ],
      [
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
      'Shift plannerShift planner: what it does.',
      'Betreiber',
      'Hochrisiko, angenommen',
      'Anhang III Nr. 4 Buchst. a',
      '2. Dez. 20272. Aug. 2026',
      'Weitere Angaben nötig',
    ])
    expect(rows[4]?.[4]).toBe('Nur nach einer erheblichen ÄnderungArt. 111 Abs. 2')
    expect(rows[5]?.[4]).toBe('Ab dem 2. Aug. 2030Art. 111 Abs. 2')
    expect(rows[6]?.slice(3)).toEqual(['Art. 50 Abs. 4', 'Seit dem 2. Aug. 2026', 'Entschieden'])
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
      await screen.findByRole(
        'heading',
        { level: 1, name: 'Applicant screening' },
        { timeout: FIRST_RENDER_MS },
      ),
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
    expect(
      await screen.findByRole('heading', { level: 1, name: title }, { timeout: FIRST_RENDER_MS }),
    ).toBeInTheDocument()
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
