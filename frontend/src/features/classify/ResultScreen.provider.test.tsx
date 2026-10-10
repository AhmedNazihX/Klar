// The provider layout (P23, artboard `ResultProvider`) on recorded provider results, with
// Supabase configured: the duties in C9's three groups with their ticks (P24's duty_progress),
// what makes it lighter from the company profile's size class, "You also use it" for a provider
// that is also the deployer, and the Chapter V note on a system built on a general-purpose model.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import { userDataOverviewKey } from '@/hooks/use-user-data-overview'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { CLASSIFICATIONS_URL, toolRow } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import {
  GPAI_HIGH_RISK,
  GPAI_LIMITED,
  OWN_BRAND_PROVIDER,
  PROVIDER_ALSO_DEPLOYER,
} from '@/test/provider-fixtures'
import { SUPABASE_URL } from '@/test/supabase-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS, inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL: url } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url, anonKey: 'test-anon-key' }),
  }
})

// The first test loads the result route's chunks and signs in, which can pass FIRST_RENDER_MS
// on a loaded machine: it gets twice that, and each test three times.
const COLD_RENDER_MS = 2 * FIRST_RENDER_MS
vi.setConfig({ testTimeout: 3 * FIRST_RENDER_MS })

const DUTY_PROGRESS_URL = `${SUPABASE_URL}/rest/v1/duty_progress`
const RUN_ID = '0a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c01'
const TOOL_NAME = 'Screening'
// Axe can't compute contrast over glass in jsdom (AppFrame.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

const GPAI_NOTE_EN =
  "The model's maker has its own duties under Chapter V (Art. 53). Klar doesn't assess those."
const GPAI_NOTE_DE =
  'Der Anbieter des Modells hat eigene Pflichten nach Kapitel V (Art. 53). Diese bewertet Klar nicht.'
const SME_FORM =
  "As an SME, you may provide the technical documentation in Annex IV in a simplified form, on a form the Commission sets. The Commission hasn't published the form yet; until it does, document the full Annex IV."
const SMC_FORM =
  "As a small mid-cap, you may provide the technical documentation in Annex IV in a simplified form, on a form the Commission sets. The Commission hasn't published the form yet; until it does, document the full Annex IV."
const SME_FORM_DE =
  'Als KMU können Sie die technische Dokumentation nach Anhang IV in vereinfachter Weise bereitstellen, mit einem Formular der Kommission. Die Kommission hat das Formular noch nicht veröffentlicht; bis dahin dokumentieren Sie den vollen Anhang IV.'

const SWITCH_A_EN = "You put your own name or trademark on it, so you're the provider."

type Tick = { system_id: string; obligation_key: string }

let inventories: Record<string, unknown>[] = []
let tools: Record<string, unknown>[] = []
let ticks: Tick[] = []
let writes: string[] = []

beforeEach(() => {
  inventories = [inventoryRow()]
  tools = []
  ticks = []
  writes = []
  server.use(
    ...userDataHandlers(
      () => inventories,
      () => tools.length,
      () => tools,
    ),
    http.get(CLASSIFICATIONS_URL, () =>
      HttpResponse.json(
        tools.map((tool) => ({ id: RUN_ID, run_no: 1, result: tool['result'], inputs: null })),
      ),
    ),
    http.get(DUTY_PROGRESS_URL, () => HttpResponse.json(ticks)),
    http.post(DUTY_PROGRESS_URL, async ({ request }) => {
      const tick = (await request.json()) as Tick
      writes.push(`add ${tick.obligation_key}`)
      ticks = [...ticks, tick]
      return new HttpResponse(null, { status: 201 })
    }),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

/** Opens the stored tool whose latest run is `result`, with the company of size `sizeClass`
 *  (no profile row at all when undefined). */
async function openProvider(
  result: ClassificationResult,
  {
    language = 'en',
    sizeClass,
    law,
  }: {
    language?: 'en' | 'de'
    sizeClass?: 'sme' | 'smc' | 'none' | null
    law?: 'original'
  } = {},
): Promise<{ user: ReturnType<typeof userEvent.setup>; toolId: string; container: HTMLElement }> {
  await i18n.changeLanguage(language)
  inventories =
    sizeClass === undefined ? [] : [inventoryRow({ company_name: 'Duval', size_class: sizeClass })]
  const row = toolRow(TOOL_NAME, result)
  tools = [row]
  const toolId = String(row['id'])
  const user = userEvent.setup()
  const search = law ? `?law=${law}` : ''
  const client = createTestQueryClient()
  const { container } = renderRoute(`/app/inventory/${toolId}${search}`, client)
  await screen.findByRole('heading', { level: 1, name: TOOL_NAME }, { timeout: COLD_RENDER_MS })
  // The company profile has been read, so a size class that is there has been shown.
  await waitFor(() => {
    expect(client.getQueryState(userDataOverviewKey)?.status).toBe('success')
  })
  if (sizeClass !== undefined) await screen.findByText('Duval')
  return { user, toolId, container }
}

function region(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

/** The article column of each duty in a group, in order. */
function articlesIn(group: string): string[] {
  return within(region(group))
    .getAllByRole('listitem')
    .map((item) => item.lastElementChild?.lastElementChild?.lastElementChild?.textContent ?? '')
}

describe('Provider layout: duties', () => {
  it('shows the role pill and the three groups with their articles and the count', async () => {
    await openProvider(OWN_BRAND_PROVIDER)
    const summary = region('Result')
    expect(within(summary).getByText('Provider')).toBeInTheDocument()
    expect(summary).toHaveTextContent(SWITCH_A_EN)

    const duties = region('What you need to do as the provider')
    expect(
      within(duties).getByText(
        "As the provider, you're responsible for how it's designed, documented and watched after launch.",
      ),
    ).toBeInTheDocument()
    expect(await within(duties).findByText('0 of 21 done')).toBeInTheDocument()
    expect(within(region('Build it right')).getByText('Before you put it into use')).toBeVisible()
    expect(articlesIn('Build it right')).toEqual([
      'Art. 9',
      'Art. 10',
      'Art. 12',
      'Art. 13',
      'Art. 14',
      'Art. 15',
      'Art. 16(l)',
    ])
    expect(within(region('Prove it')).getByText('Documents and checks')).toBeVisible()
    expect(articlesIn('Prove it')).toEqual([
      'Art. 16(b)',
      'Art. 16(c)',
      'Art. 11(1)',
      'Art. 16(f)',
      'Art. 16(g)',
      'Art. 16(h)',
      'Art. 16(i)',
      'Art. 16(k)',
    ])
    expect(within(region('After launch')).getByText("For as long as it's in use")).toBeVisible()
    expect(articlesIn('After launch')).toEqual([
      'Art. 4(1)',
      'Art. 16(d)',
      'Art. 16(e)',
      'Art. 16(j)',
      'Art. 72(1)',
      'Art. 73(1)',
    ])
    // A provider only: no other role's duties, no "You also use it", no Chapter V note.
    expect(screen.queryByRole('region', { name: 'You also use it' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'What you need to do' })).toBeNull()
    expect(screen.queryByText(GPAI_NOTE_EN)).toBeNull()
  })

  it('opens the technical documentation as a skeleton, for this tool', async () => {
    const { toolId } = await openProvider(OWN_BRAND_PROVIDER)
    const prove = region('Prove it')
    const link = within(prove).getByRole('link', { name: 'Open skeleton' })
    expect(link).toHaveAttribute(
      'href',
      `/app/documents/annex_iv_technical_documentation?tool=${toolId}`,
    )
    expect(within(prove).getAllByRole('link')).toHaveLength(2)
    expect(within(prove).getByRole('link', { name: 'Draft document' })).toHaveAttribute(
      'href',
      `/app/documents/art_17_quality_management?tool=${toolId}`,
    )
  })

  it('shows saved ticks in the count and saves a new one', async () => {
    const { user, toolId } = await openProvider(OWN_BRAND_PROVIDER)
    ticks = [{ system_id: toolId, obligation_key: 'hr-provider-risk-management' }]
    // The ticks were read before this one was saved elsewhere: tick another box here.
    const box = within(region('After launch')).getByRole('checkbox', {
      name: 'Monitor how it performs in use',
    })
    await user.click(box)
    expect(writes).toEqual(['add hr-provider-post-market-monitoring'])
    const duties = region('What you need to do as the provider')
    expect(await within(duties).findByText('2 of 21 done')).toBeInTheDocument()
    expect(
      within(region('Build it right')).getByRole('checkbox', {
        name: 'Run a risk management system for its whole life',
      }),
    ).toBeChecked()
  })

  it('marks legacy duties as P5 does (item 24)', async () => {
    const obligations = (OWN_BRAND_PROVIDER.obligations ?? []).map((duty) =>
      duty.article === 'art:9' ? { ...duty, legacy: 'legacy_unchanged' as const } : duty,
    )
    await openProvider({ ...OWN_BRAND_PROVIDER, obligations })
    const build = region('Build it right')
    expect(within(build).getByText('Only after a significant change')).toBeInTheDocument()
    expect(within(build).getAllByText('Art. 111(2)')).toHaveLength(1)
  })

  it('renders the groups in German', async () => {
    await openProvider(PROVIDER_ALSO_DEPLOYER, { language: 'de' })
    expect(within(region('Ergebnis')).getByText('Anbieter')).toBeInTheDocument()
    const duties = region('Was Sie als Anbieter tun müssen')
    expect(
      within(duties).getByText(
        'Als Anbieter sind Sie dafür verantwortlich, wie es gestaltet, dokumentiert und nach dem Start überwacht wird.',
      ),
    ).toBeInTheDocument()
    expect(await within(duties).findByText('0 von 22 erledigt')).toBeInTheDocument()
    expect(within(region('Richtig bauen')).getByText('Bevor Sie es einsetzen')).toBeVisible()
    expect(within(region('Nachweisen')).getByText('Dokumente und Prüfungen')).toBeVisible()
    expect(within(region('Nach dem Start')).getByText('Solange es im Einsatz ist')).toBeVisible()
    expect(
      within(region('Nachweisen')).getByRole('link', { name: 'Gerüst öffnen' }),
    ).toBeInTheDocument()
  })
})

describe('Provider layout: ticks that fail', () => {
  it.each([
    ['en', "Klar couldn't load the duties you ticked off."],
    ['de', 'Klar konnte die abgehakten Pflichten nicht laden.'],
  ] as const)('says so when the ticks cannot be read (%s)', async (language, message) => {
    server.use(
      http.get(DUTY_PROGRESS_URL, () => HttpResponse.json({ message: 'down' }, { status: 500 })),
    )
    await openProvider(OWN_BRAND_PROVIDER, { language })
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('says so when a tick cannot be saved, and unticks the box', async () => {
    server.use(
      http.post(DUTY_PROGRESS_URL, () =>
        HttpResponse.json({ message: 'refused' }, { status: 500 }),
      ),
    )
    const { user } = await openProvider(OWN_BRAND_PROVIDER)
    const box = within(region('Build it right')).getByRole('checkbox', {
      name: 'Run a risk management system for its whole life',
    })
    await user.click(box)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Klar couldn't save that tick. Please try again.",
    )
    expect(box).not.toBeChecked()
  })
})

describe('Provider layout: why the company is the provider', () => {
  it.each([
    [
      'en',
      'Result',
      "You build it on another company's general-purpose AI model, so you're the provider of your system.",
    ],
    [
      'de',
      'Ergebnis',
      'Sie bauen es auf dem KI-Modell mit allgemeinem Verwendungszweck eines anderen Unternehmens auf, deshalb sind Sie Anbieter Ihres Systems.',
    ],
  ] as const)('names the GPAI build route (%s)', async (language, name, sentence) => {
    await openProvider(GPAI_HIGH_RISK, { language })
    expect(region(name)).toHaveTextContent(sentence)
  })

  it.each([
    [
      'en',
      'Result',
      "You develop it, or have it developed, and supply or use it under your own name, so you're the provider.",
    ],
    [
      'de',
      'Ergebnis',
      'Sie entwickeln es oder lassen es entwickeln und bringen es unter Ihrem eigenen Namen in Verkehr oder nehmen es so in Betrieb, deshalb sind Sie Anbieter.',
    ],
  ] as const)(
    'names Art. 3(3) for a provider in its own right (%s)',
    async (language, name, sentence) => {
      // No Art. 25(1) switch: the company is the provider from the start.
      await openProvider({ ...OWN_BRAND_PROVIDER, role_switch_reason: null }, { language })
      expect(region(name)).toHaveTextContent(sentence)
    },
  )

  it.each([
    ['en', 'Result', SWITCH_A_EN, OWN_BRAND_PROVIDER],
    [
      'de',
      'Ergebnis',
      'Sie versehen es mit Ihrem eigenen Namen oder Ihrer Handelsmarke, deshalb sind Sie Anbieter.',
      OWN_BRAND_PROVIDER,
    ],
    [
      'en',
      'Result',
      "You changed what it's meant for so that it became high-risk, so you're the provider.",
      PROVIDER_ALSO_DEPLOYER,
    ],
    [
      'de',
      'Ergebnis',
      'Sie haben seine Zweckbestimmung so verändert, dass es zu einem Hochrisiko-System wurde, deshalb sind Sie Anbieter.',
      PROVIDER_ALSO_DEPLOYER,
    ],
  ] as const)(
    'names the Art. 25(1) point of a switch (%s): %s',
    async (language, name, sentence, result) => {
      await openProvider(result, { language })
      expect(region(name)).toHaveTextContent(sentence)
    },
  )
})

describe('Provider layout: legal review', () => {
  it.each([
    [
      'en',
      'Result',
      'Provider duties are substantial. We recommend a legal review before you plan the work.',
    ],
    [
      'de',
      'Ergebnis',
      'Die Anbieterpflichten sind umfangreich. Wir empfehlen eine rechtliche Prüfung, bevor Sie die Arbeit planen.',
    ],
  ] as const)("uses the provider layout's line (%s)", async (language, name, line) => {
    await openProvider(OWN_BRAND_PROVIDER, { language })
    expect(within(region(name)).getByText(line)).toBeVisible()
  })
})

describe('Provider layout: a legally ambiguous result', () => {
  it('keeps the standard layout, without the provider pill', async () => {
    // Its layout is the ambiguous one (P22), which draws no role pill.
    await openProvider({ ...OWN_BRAND_PROVIDER, status: 'legally_ambiguous' })
    const summary = region('Result')
    expect(within(summary).getByText('Legally ambiguous')).toBeInTheDocument()
    expect(within(summary).queryByText('Provider')).toBeNull()
    expect(summary).not.toHaveTextContent(SWITCH_A_EN)
    expect(screen.queryByRole('region', { name: 'What you need to do as the provider' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'What makes it lighter' })).toBeNull()
  })
})

describe('Provider layout: what makes it lighter', () => {
  it.each([
    ['sme', SME_FORM],
    ['smc', SMC_FORM],
  ] as const)(
    'shows the simplified form for a company that counts as %s',
    async (sizeClass, text) => {
      await openProvider(OWN_BRAND_PROVIDER, { sizeClass })
      const lighter = region('What makes it lighter')
      expect(within(lighter).getByText(text)).toBeInTheDocument()
      expect(within(lighter).getByText('A simpler documentation form')).toBeInTheDocument()
      expect(within(lighter).getByText('Art. 11(1)')).toBeInTheDocument()
    },
  )

  it('shows the SME form in German', async () => {
    await openProvider(PROVIDER_ALSO_DEPLOYER, { language: 'de', sizeClass: 'sme' })
    const lighter = region('Was es leichter macht')
    expect(within(lighter).getByText(SME_FORM_DE)).toBeInTheDocument()
    expect(within(lighter).getByText('Ein vereinfachtes Dokumentationsformular')).toBeVisible()
    expect(within(lighter).getByText('Art. 11 Abs. 1')).toBeVisible()
  })

  it.each([['none'], [null], [undefined]] as const)(
    'shows no simplified form for size class %s (undefined: no profile)',
    async (sizeClass) => {
      await openProvider(OWN_BRAND_PROVIDER, { sizeClass })
      const lighter = region('What makes it lighter')
      expect(within(lighter).queryByText('A simpler documentation form')).toBeNull()
      expect(lighter).not.toHaveTextContent('simplified')
    },
  )

  it('names no small mid-cap under the original text', async () => {
    await openProvider(OWN_BRAND_PROVIDER, { sizeClass: 'smc', law: 'original' })
    const lighter = region('What makes it lighter')
    expect(lighter).not.toHaveTextContent(/mid-cap|simplified/)
  })

  it.each([
    [
      'en',
      'What makes it lighter',
      'For systems under Annex III point 4, you assess conformity yourself, by internal control.',
      'Art. 43(2), Annex VI',
      OWN_BRAND_PROVIDER,
    ],
    [
      'de',
      'Was es leichter macht',
      'Für Systeme nach Anhang III Nr. 5 bewerten Sie die Konformität selbst, durch eine interne Kontrolle.',
      'Art. 43 Abs. 2, Anhang VI',
      PROVIDER_ALSO_DEPLOYER,
    ],
  ] as const)(
    'shows the internal-control route for an Annex III point 2 to 8 system (%s)',
    async (language, heading, text, reference, result) => {
      await openProvider(result, { language })
      const lighter = region(heading)
      expect(within(lighter).getByText(text)).toBeVisible()
      expect(within(lighter).getByText(reference)).toBeVisible()
    },
  )

  it('leaves the panel out for an Annex III point 1 system without a size class', async () => {
    await openProvider({ ...OWN_BRAND_PROVIDER, annex_point: 'annex:III:1:a' })
    expect(screen.queryByRole('region', { name: 'What makes it lighter' })).toBeNull()
  })
})

describe('Provider layout: You also use it', () => {
  it('shows the deployer duties and links to them when the result keeps the deployer role', async () => {
    await openProvider(PROVIDER_ALSO_DEPLOYER)
    const also = region('You also use it')
    expect(
      within(also).getByText(
        'You use the system yourselves too, so the deployer duties apply as well.',
      ),
    ).toBeVisible()
    expect(within(also).getByRole('link', { name: 'See the deployer duties' })).toHaveAttribute(
      'href',
      '#role-duties',
    )
    const deployer = region('What you need to do as the deployer')
    expect(deployer).toHaveAttribute('id', 'role-duties')
    expect(within(deployer).getByText('Art. 26(1)')).toBeInTheDocument()
    expect(await within(deployer).findByText('0 of 12 done')).toBeInTheDocument()
    // A deployer duty isn't in a provider group.
    const provider = region('What you need to do as the provider')
    expect(within(provider).queryByText('Art. 26(1)')).toBeNull()
  })

  it('says it in German', async () => {
    await openProvider(PROVIDER_ALSO_DEPLOYER, { language: 'de' })
    const also = region('Sie nutzen es auch')
    expect(
      within(also).getByText(
        'Sie nutzen das System auch selbst, daher gelten zusätzlich die Pflichten als Betreiber.',
      ),
    ).toBeVisible()
    expect(within(also).getByRole('link', { name: 'Zu den Betreiberpflichten' })).toBeVisible()
    expect(region('Was Sie als Betreiber tun müssen')).toBeInTheDocument()
  })

  it('stays out without also_role', async () => {
    await openProvider(OWN_BRAND_PROVIDER)
    expect(screen.queryByRole('region', { name: 'You also use it' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'See the deployer duties' })).toBeNull()
  })
})

describe('Chapter V note (decision 026 item 17)', () => {
  it.each([
    ['en', GPAI_NOTE_EN, 'What you need to do as the provider'],
    ['de', GPAI_NOTE_DE, 'Was Sie als Anbieter tun müssen'],
  ] as const)('shows on a high-risk GPAI-based result (%s)', async (language, note, panel) => {
    await openProvider(GPAI_HIGH_RISK, { language })
    expect(within(region(panel)).getByText(note)).toBeVisible()
  })

  it.each([
    ['en', GPAI_NOTE_EN, 'What you need to do'],
    ['de', GPAI_NOTE_DE, 'Was Sie tun müssen'],
  ] as const)('shows on a limited-risk GPAI-based result (%s)', async (language, note, panel) => {
    await openProvider(GPAI_LIMITED, { language })
    expect(within(region(panel)).getByText(note)).toBeVisible()
  })

  it('stays out while the GPAI question is still open', async () => {
    const asked = {
      id: 'builds_on_gpai',
      text: 'Is the system built on a general-purpose AI model from another provider?',
      about: 'art:3:68',
    }
    await openProvider({
      ...GPAI_HIGH_RISK,
      follow_up_questions: [...(GPAI_HIGH_RISK.follow_up_questions ?? []), asked],
    })
    await waitFor(() => {
      expect(region('What you need to do as the provider')).toBeInTheDocument()
    })
    expect(screen.queryByText(GPAI_NOTE_EN)).toBeNull()
  })
})

describe('Provider layout: accessibility', () => {
  it('has no axe violations', async () => {
    const { container } = await openProvider(PROVIDER_ALSO_DEPLOYER, { sizeClass: 'sme' })
    expect(within(region('What makes it lighter')).getByText(SME_FORM)).toBeVisible()
    const results = await axe(container, AXE_OPTIONS)
    expect(results.violations).toEqual([])
  })
})
