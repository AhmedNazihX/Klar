import { describe, expect, it } from 'vitest'

import type { ClassificationResult } from '@/api'
import type { CheckedTool } from '@/features/inventory/tool-facts'
import { ambiguousResult, prohibitedResult } from '@/test/inventory-fixtures'
import {
  decidedHighRisk,
  legacyForPublicAuthorities,
  legacyMarkedDeployer,
  limitedRisk,
  minimalRisk,
  outOfScope,
  WORKED_EXAMPLE,
} from '@/test/classify-fixtures'
import { tickKey } from '@/lib/duty-progress'

import {
  dateSections,
  dutiesProgress,
  nextDate,
  overallProgress,
  toolCards,
  toolProgress,
  toolsWithoutDuties,
  type DateSection,
} from './obligation-list'

/** After Art. 50 started to apply (2 Aug 2026), before the amended Annex III date. */
const TODAY = new Date(2026, 9, 7, 12)

function tool(name: string, result: ClassificationResult): CheckedTool {
  return {
    toolId: `tool-${name}`,
    name,
    description: `${name}: what it does.`,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult: false,
    runNo: 1,
  }
}

const SCREENING = tool('Applicant screening', decidedHighRisk())
const MOOD = tool('Call mood scoring', prohibitedResult())
const PHOTOS = tool('Product photo generator', limitedRisk())
const OLD_SCREENER = tool('Old screener', legacyMarkedDeployer())
const BENEFITS = tool('Benefits checker', legacyForPublicAuthorities())
const SHIFTS = tool('Shift planner', WORKED_EXAMPLE)
const CV = tool('CV data extraction', ambiguousResult())
const ROUTES = tool('Route optimisation', minimalRisk())
const INVOICES = tool('Invoice matching', outOfScope())

/** Each section as its kind (and date) with its tools and how many duties each lists there. */
function outline(sections: readonly DateSection[]): string[] {
  return sections.map((section) => {
    const when =
      section.kind === 'route'
        ? ` ${section.route} ${section.amended}/${section.original}`
        : 'date' in section
          ? ` ${section.date}`
          : ''
    const tools = section.tools.map(({ tool: t, duties }) => `${t.name ?? ''}:${duties.length}`)
    return `${section.kind}${when} [${tools.join(', ')}]`
  })
}

describe('By date', () => {
  it('puts each duty under the date it applies from, with the route date swapping', () => {
    const sections = dateSections([MOOD, SCREENING, PHOTOS, OLD_SCREENER, ROUTES], TODAY)
    expect(outline(sections)).toEqual([
      'stop [Call mood scoring:0]',
      'since 2025-02-02 [Applicant screening:1, Product photo generator:1, Old screener:1, Route optimisation:1]',
      'since 2026-08-02 [Product photo generator:1]',
      'route annex_iii 2027-12-02/2026-08-02 [Applicant screening:10]',
      // Art. 111(2): the marked duties wait for a significant change.
      'afterChange [Old screener:10]',
    ])
  })

  it('keeps a high-risk provider whole where its route duties start, its 2030 date included', () => {
    expect(outline(dateSections([BENEFITS], TODAY))).toEqual([
      'from 2030-08-02 [Benefits checker:3]',
    ])
  })

  it('says what a dated section holds, and sets a plain section apart from a route twin', () => {
    // An Art. 6(4) duty dated like the Annex III route: its section has the route's date.
    const [literacy] = decidedHighRisk().obligations ?? []
    if (!literacy) throw new Error('The fixture has duties.')
    const assessment = {
      ...literacy,
      key: 'art-6-4',
      article: 'art:6:4',
      applies_from: '2027-12-02',
    }
    const chat = tool('Customer chat assistant', {
      ...limitedRisk(),
      obligations: [...(limitedRisk().obligations ?? []), assessment],
    })
    const mixed = tool('Mixed', {
      ...limitedRisk(),
      obligations: [assessment, { ...assessment, key: 'art-4-x', article: 'art:4' }],
    })
    const categories = (tools: CheckedTool[]) =>
      dateSections(tools, TODAY).map((section) =>
        'category' in section
          ? `${section.kind} ${section.date} ${JSON.stringify(section.category)}`
          : section.kind,
      )
    expect(categories([SCREENING, chat])).toEqual([
      'since 2025-02-02 {"kind":"article","article":"art:4:1"}',
      'since 2026-08-02 {"kind":"transparency"}',
      'route',
      'from 2027-12-02 {"kind":"article","article":"art:6:4"}',
    ])
    // Two articles: no single one to name, so "other duties" beside the route twin; none alone.
    expect(categories([SCREENING, mixed]).at(-1)).toBe('from 2027-12-02 {"kind":"other"}')
    expect(categories([mixed])).toEqual(['from 2027-12-02 null'])
  })

  it('lists no section for tools without specific duties, which are named apart', () => {
    expect(dateSections([INVOICES], TODAY)).toEqual([])
    expect(toolsWithoutDuties([SCREENING, ROUTES, INVOICES])).toEqual([ROUTES, INVOICES])
  })
})

describe('By tool', () => {
  it('regroups the same duties under their tools', () => {
    const tools = [MOOD, SCREENING, PHOTOS, OLD_SCREENER, BENEFITS, CV]
    const byDate = dateSections(tools, TODAY).flatMap((section) =>
      section.tools.flatMap(({ tool: t, duties }) => duties.map((d) => `${t.toolId}:${d.article}`)),
    )
    const byTool = toolCards(tools).flatMap(({ tool: t, duties }) =>
      duties.map((d) => `${t.toolId}:${d.article}`),
    )
    expect(byTool).toHaveLength(byDate.length)
    expect(new Set(byTool)).toEqual(new Set(byDate))
    expect(toolCards(tools).map(({ tool: t }) => t.name)).toEqual([
      'Call mood scoring',
      'Applicant screening',
      'Product photo generator',
      'Old screener',
      'Benefits checker',
      'CV data extraction',
    ])
  })

  it('lists a tool without duties too, as By date does under "No specific duties"', () => {
    expect(
      toolCards([SCREENING, ROUTES, INVOICES]).map(
        ({ tool: t, duties }) => `${t.name ?? ''}:${duties.length}`,
      ),
    ).toEqual([
      'Applicant screening:11',
      // Minimal risk: AI literacy (Art. 4) only.
      'Route optimisation:1',
      // Out of scope: no duties, whatever its result lists.
      'Invoice matching:0',
    ])
  })
})

describe('Progress', () => {
  it('counts the ticked duties per tool and overall, each key once', () => {
    const ticks = [
      { toolId: SCREENING.toolId, obligationKey: 'hr-deployer-logs' },
      { toolId: SCREENING.toolId, obligationKey: 'ai-literacy' },
      { toolId: PHOTOS.toolId, obligationKey: 'transparency-deep-fake' },
      // Another tool's tick doesn't count here.
      { toolId: OLD_SCREENER.toolId, obligationKey: 'hr-deployer-instructions' },
    ]
    expect(toolProgress(SCREENING, ticks)).toEqual({ done: 2, total: 11 })
    // A card counts the duties it lists: Art. 4's section holds one of Applicant screening's.
    const literacyOnly = (SCREENING.result.obligations ?? []).slice(0, 1)
    expect(dutiesProgress(SCREENING.toolId, literacyOnly, ticks)).toEqual({ done: 1, total: 1 })
    expect(toolProgress(PHOTOS, ticks)).toEqual({ done: 1, total: 2 })
    expect(overallProgress([SCREENING, PHOTOS], ticks)).toEqual({ done: 3, total: 13 })
  })

  it('has nothing to tick on an informational line or a duty stored without its key', () => {
    const [literacy] = decidedHighRisk().obligations ?? []
    if (!literacy) throw new Error('The fixture has duties.')
    expect(tickKey(literacy)).toBe('ai-literacy')
    expect(tickKey({ ...literacy, is_informational: true })).toBeNull()
    expect(tickKey({ ...literacy, key: undefined })).toBeNull()
  })
})

describe('Next date', () => {
  it('is the earliest date still ahead, naming decided tools and counting assumed ones', () => {
    const next = nextDate([PHOTOS, SCREENING, SHIFTS, CV, BENEFITS, MOOD], TODAY, 'amended')
    expect(next?.date).toBe('2027-12-02')
    expect(next?.tools.map((t) => t.name)).toEqual(['Applicant screening'])
    expect(next?.assumed).toBe(2)
  })

  it('under the original text, skips the route date that has come', () => {
    // Annex III's original date (2 August 2026) has come: next is Art. 111(2)'s 2030 date.
    const next = nextDate([SCREENING, BENEFITS], TODAY, 'original')
    expect(next?.date).toBe('2030-08-02')
    expect(next?.tools.map((t) => t.name)).toEqual(['Benefits checker'])
    expect(nextDate([SCREENING, PHOTOS], TODAY, 'original')).toBeNull()
  })

  it('waits for no date a duty only gets after a significant change', () => {
    expect(nextDate([OLD_SCREENER], TODAY, 'amended')).toBeNull()
  })
})
