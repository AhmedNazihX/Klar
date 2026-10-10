import { describe, expect, it } from 'vitest'

import type { ClassificationResult } from '@/api'
import type { InventoryTool } from '@/lib/inventory'
import {
  annexINeedsInfo,
  decidedHighRisk,
  legacyForPublicAuthorities,
  legacyMarkedDeployer,
  limitedRisk,
  minimalRisk,
  outOfScope,
  WORKED_EXAMPLE,
} from '@/test/classify-fixtures'
import { ambiguousResult, prohibitedResult, toolId } from '@/test/inventory-fixtures'

import {
  appliesFrom,
  basisReferences,
  isoDay,
  openQuestionCount,
  sortTools,
  whatItDoes,
} from './tool-facts'

/** The day Art. 50 started to apply, and the day before (Art. 113). */
const ART_50_START = new Date(2026, 7, 2)
const BEFORE_ART_50 = new Date(2026, 7, 1)
const TODAY = new Date(2026, 9, 7)

function tool(name: string, result: ClassificationResult | null): InventoryTool {
  return {
    toolId: toolId(),
    name,
    description: name,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult: false,
    runNo: 1,
  }
}

describe('appliesFrom', () => {
  it('gives a high-risk result its route dates under both texts', () => {
    expect(appliesFrom(decidedHighRisk(), TODAY)).toEqual({
      kind: 'route',
      amended: '2027-12-02',
      original: '2026-08-02',
    })
  })

  it('reads "only after a significant change" when Art. 111(2) marks every route duty', () => {
    expect(appliesFrom(legacyMarkedDeployer(), TODAY)).toEqual({ kind: 'afterChange' })
  })

  it('reads 2 August 2030 for a legacy system meant for public authorities', () => {
    expect(appliesFrom(legacyForPublicAuthorities(), TODAY)).toEqual({
      kind: 'legacyFrom',
      date: '2030-08-02',
    })
  })

  it('dates limited risk by its Art. 50 duty: "since" from its first day, "from" before', () => {
    // The result also carries Art. 4's duty (2 Feb 2025), which doesn't date the class.
    expect(appliesFrom(limitedRisk(), ART_50_START)).toEqual({ kind: 'since', date: '2026-08-02' })
    expect(appliesFrom(limitedRisk(), BEFORE_ART_50)).toEqual({ kind: 'from', date: '2026-08-02' })
  })

  it('dates a prohibited result by its duties when it carries any', () => {
    const banned: ClassificationResult = {
      ...prohibitedResult(),
      // Art. 4's duty, the one limited risk carries besides Art. 50.
      obligations: (limitedRisk().obligations ?? []).filter((duty) => duty.article === 'art:4:1'),
    }
    expect(appliesFrom(banned, TODAY)).toEqual({ kind: 'since', date: '2025-02-02' })
  })

  it.each([
    ['minimal risk', minimalRisk()],
    ['out of scope', outOfScope()],
    ['a prohibited result with no dated duty', prohibitedResult()],
  ])('names no date for %s', (_, result) => {
    expect(appliesFrom(result, TODAY)).toEqual({ kind: 'none' })
  })
})

describe('basisReferences', () => {
  it.each<[string, ClassificationResult, string[], string[]]>([
    ['high-risk', decidedHighRisk(), ['Annex III 4(a)'], ['Anhang III Nr. 4 Buchst. a']],
    [
      'ambiguous high-risk',
      ambiguousResult(),
      ['Annex III 4(a)', 'Art. 6(3)'],
      ['Anhang III Nr. 4 Buchst. a', 'Art. 6 Abs. 3'],
    ],
    ['prohibited', prohibitedResult(), ['Art. 5(1)(f)'], ['Art. 5 Abs. 1 Buchst. f']],
    ['limited risk', limitedRisk(), ['Art. 50(4)'], ['Art. 50 Abs. 4']],
    [
      'limited risk under two Art. 50 duties',
      { ...limitedRisk(), transparency_duties: ['art:50:1', 'art:50:4'] },
      ['Art. 50'],
      ['Art. 50'],
    ],
    ['out of scope', outOfScope(), ['Art. 3(1)'], ['Art. 3 Abs. 1']],
    ['minimal risk', minimalRisk(), [], []],
  ])('names what %s rests on, EN and DE', (_, result, en, de) => {
    expect(basisReferences(result, 'en')).toEqual(en)
    expect(basisReferences(result, 'de')).toEqual(de)
  })
})

describe('openQuestionCount', () => {
  it('counts the checks that paused on a missing fact', () => {
    expect(openQuestionCount(WORKED_EXAMPLE)).toBe(1)
    const twoPaused: ClassificationResult = {
      ...annexINeedsInfo(),
      steps: WORKED_EXAMPLE.steps.map((step) =>
        step.step === 'high_risk'
          ? { ...step, status: 'needs_more_information', missing_fact: { id: 'q', text: 'Q?' } }
          : step,
      ),
    }
    expect(openQuestionCount(twoPaused)).toBe(2)
  })
})

describe('sortTools', () => {
  it('puts the strictest class first and tools without a result last, else keeps the order', () => {
    const tools = [
      tool('Unchecked', null),
      tool('Minimal', minimalRisk()),
      tool('High A', decidedHighRisk()),
      tool('Prohibited', prohibitedResult()),
      tool('Out', outOfScope()),
      tool('High B', WORKED_EXAMPLE),
      tool('Limited', limitedRisk()),
    ]
    expect(sortTools(tools).map((entry) => entry.name)).toEqual([
      'Prohibited',
      'High A',
      'High B',
      'Limited',
      'Minimal',
      'Out',
      'Unchecked',
    ])
  })
})

describe('whatItDoes', () => {
  it("states what the tool does from the facts its check used, not the description's opening", () => {
    const checked = {
      ...tool('Applicant screening', WORKED_EXAMPLE),
      description: "We're a 40-person logistics company. We use a tool that reads applications.",
    }
    expect(whatItDoes(checked)).toBe(
      'The tool reads job applications, scores them, and shows HR a ranked shortlist.',
    )
  })

  it('leaves out an assumed fact, which says what the description does not', () => {
    const assumedOnly: ClassificationResult = {
      ...WORKED_EXAMPLE,
      steps: WORKED_EXAMPLE.steps.map((step) =>
        step.step === 'prohibited'
          ? {
              ...step,
              facts_used: [{ text: 'It is not described as scoring.', evidence: 'assumed' }],
            }
          : step,
      ),
    }
    const checked = {
      ...tool('Scorer', assumedOnly),
      description: 'Scores people. It is new.\nMore.',
    }
    expect(whatItDoes(checked)).toBe('Scores people. It is new.')
  })

  it.each([
    ['its first line', '  Ranks applicants. Uses scores.\nMore.', 'Ranks applicants. Uses scores.'],
    ['a line without a full stop', 'Ranks applicants\nUses scores.', 'Ranks applicants'],
    [
      'past "e.g."',
      'Ranks applicants, e.g. for sales roles. Uses scores.',
      'Ranks applicants, e.g. for sales roles. Uses scores.',
    ],
    [
      'past "z. B."',
      'Bewertet Bewerbungen, z. B. für den Vertrieb.\nMehr.',
      'Bewertet Bewerbungen, z. B. für den Vertrieb.',
    ],
  ])("reads an unchecked tool's description: %s", (_, description, what) => {
    expect(whatItDoes({ ...tool('Draft', null), description })).toBe(what)
  })
})

describe('helpers', () => {
  it('writes today as the calendar day', () => {
    expect(isoDay(new Date(2026, 0, 5, 23, 30))).toBe('2026-01-05')
  })
})
