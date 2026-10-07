import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import {
  ANNEX_I_QUESTION,
  annexINeedsInfo,
  decidedHighRisk,
  legacyForPublicAuthorities,
  legacyMarked,
  legacyMarkedDeployer,
  limitedRisk,
  minimalRisk,
  OUT_OF_SCOPE_DECISION,
  outOfScope,
  withRole,
  WORKED_EXAMPLE,
  WORKED_EXAMPLE_DESCRIPTION,
} from '@/test/classify-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { classificationRunOptions, type ClassificationRun } from './classification-store'

const TOOL_ID = 'applicant-screening'
const AI_NOTICE = 'Guidance, not legal advice. Klar is an AI system.'
const NOTICE_DE = 'Orientierungshilfe, keine Rechtsberatung. Klar ist ein KI-System.'
// Axe can't compute contrast over glass in jsdom (AppFrame.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

async function openResult(
  result: ClassificationResult,
  { view, language = 'en' }: { view?: 'reviewer'; language?: 'en' | 'de' } = {},
) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
  }
  client.setQueryData(classificationRunOptions(TOOL_ID).queryKey, run)
  const path = `/app/inventory/${TOOL_ID}${view ? `?view=${view}` : ''}`
  const rendered = renderRoute(path, client)
  await screen.findByRole('heading', { level: 1, name: 'Applicant screening' })
  return rendered
}

function todoList(language: 'en' | 'de'): HTMLElement {
  return screen.getByRole('region', {
    name: language === 'en' ? 'What you need to do' : 'Was Sie tun müssen',
  })
}

function stepRows(): HTMLElement[] {
  const section = screen.getByRole('region', { name: 'How Klar got here' })
  return within(section).getAllByRole('button', { expanded: false })
}

describe('Result summary', () => {
  it('shows the class, the role and Annex point, and the date duties apply from', async () => {
    await openResult(decidedHighRisk())
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('High-risk')).toBeInTheDocument()
    expect(within(summary).getByText('Decided')).toBeInTheDocument()
    expect(summary).toHaveTextContent(
      "You're the deployer. The tool is listed in Annex III 4(a): recruitment and selection of people.",
    )
    expect(within(summary).getByText('2 December 2027')).toBeInTheDocument()
    expect(summary).toHaveTextContent(
      'For a high-risk result, we recommend a legal review before you rely on it.',
    )
    expect(
      screen.getByText(/Checked on 6 October 2026 against the consolidated AI Act of 27 July 2026/),
    ).toBeVisible()
  })

  it('lists every step collapsed, in the Act order, with its provision', async () => {
    await openResult(decidedHighRisk())
    const names = stepRows().map((row) => row.querySelector('span')?.textContent)
    expect(names).toEqual([
      'Facts',
      'Role',
      '1 Scope',
      '2 Prohibited practices',
      '3 High-risk',
      '4 Transparency',
      'Duties',
    ])
    expect(stepRows()[4]).toHaveTextContent('Yes: recruitment and selection of people')
    expect(stepRows()[4]).toHaveTextContent('Annex III 4(a), Art. 6(2), Art. 6(3)')
    // Collapsed: no step's decision or quote is on screen.
    expect(screen.queryByRole('article')).toBeNull()
    expect(screen.queryByText(/AI systems intended to be used for the recruitment/)).toBeNull()
  })

  it('opens one step in full: its decision, facts with evidence tags and quoted provisions', async () => {
    const user = userEvent.setup()
    await openResult(decidedHighRisk())
    await user.click(screen.getByRole('button', { name: /^3 High-risk/ }))

    const card = screen.getByRole('article')
    expect(within(card).getByRole('heading', { name: '3 High-risk' })).toBeInTheDocument()
    expect(card).toHaveTextContent(
      'High-risk: the system is used as listed in Annex III point 4(a)',
    )
    expect(within(card).getAllByText('Stated').length).toBeGreaterThan(0)
    expect(
      within(card).getByText(/AI systems intended to be used for the recruitment/),
    ).toBeVisible()
    expect(within(card).getByText('Annex III 4(a), English')).toBeVisible()
    expect(screen.getByRole('button', { name: /^3 High-risk/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('shows the duties as a to-do list and the facts the result rests on', async () => {
    await openResult(decidedHighRisk())
    const todo = screen.getByRole('region', { name: 'What you need to do' })
    expect(
      within(todo).getByRole('checkbox', {
        name: 'Put trained people in charge of reviewing its output',
      }),
    ).toBeInTheDocument()
    expect(within(todo).getByText('Art. 26(11)')).toBeInTheDocument()
    expect(within(todo).getByText('Only if: You control the input data.')).toBeInTheDocument()
    const facts = screen.getByRole('complementary', { name: 'The result rests on' })
    expect(within(facts).getAllByRole('button', { name: 'Confirm' }).length).toBeGreaterThan(0)
  })

  it.each([
    ['en', 'Put trained people in charge of reviewing its output', 'Draft document'],
    ['de', 'Geschulten Personen die menschliche Aufsicht übertragen', 'Dokument entwerfen'],
  ] as const)(
    "names each duty by C9's label and links its draft document (%s)",
    async (language, label, link) => {
      await openResult(decidedHighRisk(), { language })
      const todo = todoList(language)
      const oversight = within(todo).getByRole('checkbox', { name: label }).closest('li')
      expect(within(oversight as HTMLElement).getByRole('link', { name: link })).toHaveAttribute(
        'href',
        '/app/documents/art_26_2_oversight',
      )
      // Oversight, the workers' notice and the notice to the people affected have templates.
      expect(within(todo).getAllByRole('link', { name: link })).toHaveLength(3)
    },
  )

  it('confirms an assumed fact as stated', async () => {
    const user = userEvent.setup()
    await openResult(decidedHighRisk())
    const facts = screen.getByRole('complementary', { name: 'The result rests on' })
    const before = within(facts).getAllByText('Assumed').length
    await user.click(within(facts).getAllByRole('button', { name: 'Confirm' })[0] as HTMLElement)
    expect(within(facts).getAllByText('Assumed')).toHaveLength(before - 1)
  })

  it('carries the disclaimer and the AI disclosure (Art. 50(1))', async () => {
    await openResult(decidedHighRisk())
    expect(screen.getByText(new RegExp(`^${WORKED_EXAMPLE.disclaimer}`))).toHaveTextContent(
      'CELEX 02024R1689-20260727',
    )
    expect(screen.getByText(AI_NOTICE)).toBeVisible()
    expect(
      screen.getByText('You are using an AI system. Results are guidance, not legal advice.'),
    ).toBeInTheDocument()
  })

  it('passes axe', async () => {
    const { container } = await openResult(decidedHighRisk())
    const results = await axe(container, AXE_OPTIONS)
    expect(results.violations).toEqual([])
  })

  it('opens the reviewer view from "Expand every step with quotes"', async () => {
    const user = userEvent.setup()
    const { router } = await openResult(decidedHighRisk())
    await user.click(screen.getByRole('button', { name: 'Expand every step with quotes' }))
    await expect.poll(() => router.state.location.search).toEqual({ view: 'reviewer' })
    expect(screen.getAllByRole('article').length).toBe(7)
  })
})

describe('Result reviewer view', () => {
  it('expands every step with its decision, facts, evidence tags and quotes', async () => {
    await openResult(decidedHighRisk(), { view: 'reviewer' })
    const cards = screen.getAllByRole('article')
    expect(
      cards.map((card) => within(card).getByRole('heading', { level: 2 }).textContent),
    ).toEqual([
      'Facts',
      'Role',
      '1 Scope',
      '2 Prohibited practices',
      '3 High-risk',
      '4 Transparency',
      'Duties',
    ])
    const scope = cards[2] as HTMLElement
    expect(within(scope).getByText('Decision')).toBeInTheDocument()
    expect(within(scope).getByText('Facts it rests on')).toBeInTheDocument()
    expect(within(scope).getAllByText('Assumed').length).toBeGreaterThan(0)
    expect(within(scope).getByText(/‘AI system’ means a machine-based system/)).toBeVisible()
    expect(within(scope).getByText('Art. 3(1), English')).toBeVisible()
    // The step that decided the High-risk class is the highlighted one.
    expect(cards.filter((card) => card.dataset.highlight)).toEqual([cards[4]])
  })

  it('carries the disclaimer and the AI disclosure, and offers the JSON export', async () => {
    await openResult(decidedHighRisk(), { view: 'reviewer' })
    expect(screen.getByText(new RegExp(`^${WORKED_EXAMPLE.disclaimer}`))).toBeVisible()
    expect(screen.getByText(AI_NOTICE)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Export as JSON' })).toBeInTheDocument()
  })

  it('passes axe', async () => {
    const { container } = await openResult(decidedHighRisk(), { view: 'reviewer' })
    const results = await axe(container, AXE_OPTIONS)
    expect(results.violations).toEqual([])
  })
})

describe('Result statuses', () => {
  it('labels the working assumption and asks the question that decides it (worked example)', async () => {
    await openResult(WORKED_EXAMPLE)
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('Assumed')).toBeInTheDocument()
    expect(within(summary).getByText('Needs more information')).toBeInTheDocument()
    expect(summary).toHaveTextContent('Klar assumed one fact at check 1.')
    expect(
      screen.getByRole('heading', { level: 2, name: /How does the system produce its outputs/ }),
    ).toBeInTheDocument()
  })

  it('shows a legally ambiguous result as its own status', async () => {
    await openResult({ ...decidedHighRisk(), status: 'legally_ambiguous' })
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('Assumed')).toBeInTheDocument()
    expect(within(summary).getByText('Legally ambiguous')).toBeInTheDocument()
    expect(within(summary).queryByText('Decided')).toBeNull()
  })

  it('asks the Annex I conformity question with If yes and If no (item 18)', async () => {
    await openResult(annexINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_I_QUESTION })
    expect(within(question).getByText('If yes')).toBeInTheDocument()
    expect(question).toHaveTextContent('Annex I Section A point 1. Duties from 2 August 2028')
    expect(question).toHaveTextContent(
      'If noNot high-risk on this point. The transparency check then decides whether any duties apply.',
    )
    expect(within(question).getByText('Art. 6(1), English')).toBeVisible()
    expect(within(question).getByText('Annex I Section A point 1, English')).toBeVisible()
  })
})

describe('Result variants (decision 026)', () => {
  it.each([
    ['en', "You're the importer.", 'Art. 23(1)'],
    ['de', 'Sie sind Einführer.', 'Art. 23 Abs. 1'],
  ] as const)(
    'gives an importer its role sentence and duties (%s)',
    async (language, sentence, ref) => {
      await openResult(withRole('importer'), { language })
      expect(screen.getByText(sentence)).toBeInTheDocument()
      expect(within(todoList(language)).getByText(ref)).toBeInTheDocument()
    },
  )

  it.each([
    ['en', "You're the distributor.", 'Art. 24(1)'],
    ['de', 'Sie sind Händler.', 'Art. 24 Abs. 1'],
  ] as const)(
    'gives a distributor its role sentence and duties (%s)',
    async (language, sentence, ref) => {
      await openResult(withRole('distributor'), { language })
      expect(screen.getByText(sentence)).toBeInTheDocument()
      expect(within(todoList(language)).getByText(ref)).toBeInTheDocument()
    },
  )

  it.each([
    ['en', 'Limited risk', 'Draft disclosure', 'Art. 50(4)'],
    ['de', 'Begrenztes Risiko', 'Hinweis entwerfen', 'Art. 50 Abs. 4'],
  ] as const)(
    'shows the Art. 50 duty with its drafted disclosure (%s)',
    async (language, name, link, ref) => {
      await openResult(limitedRisk(), { language })
      const summary = screen.getByRole('region', {
        name: language === 'en' ? 'Result' : 'Ergebnis',
      })
      expect(within(summary).getByText(name)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: link })).toHaveAttribute(
        'href',
        '/app/documents/art_50_4_disclosure',
      )
      expect(within(todoList(language)).getByText(ref)).toBeInTheDocument()
    },
  )

  it.each([
    ['en', 'No specific duties for this tool.', 'Art. 4(1)'],
    ['de', 'Keine besonderen Pflichten für dieses Tool.', 'Art. 4 Abs. 1'],
  ] as const)(
    'says a minimal-risk tool has no specific duties, plus Art. 4 (%s)',
    async (language, line, ref) => {
      await openResult(minimalRisk(), { language })
      expect(screen.getByText(new RegExp(`^${line}`))).toBeInTheDocument()
      expect(within(todoList(language)).getByText(ref)).toBeInTheDocument()
    },
  )

  it.each([
    ['en', 'Out of scope', "Why the AI Act doesn't apply"],
    ['de', 'Außerhalb des Anwendungsbereichs', 'Warum die KI-Verordnung nicht gilt'],
  ] as const)(
    'explains an out-of-scope result with the quote and no duty list (%s)',
    async (language, name, heading) => {
      await openResult(outOfScope(), { language })
      const summary = screen.getByRole('region', {
        name: language === 'en' ? 'Result' : 'Ergebnis',
      })
      expect(within(summary).getByText(name)).toBeInTheDocument()
      const why = screen.getByRole('region', { name: heading })
      expect(within(why).getByText(OUT_OF_SCOPE_DECISION)).toBeInTheDocument()
      expect(within(why).getByText(/‘AI system’ means a machine-based system/)).toBeVisible()
      expect(screen.queryByRole('checkbox')).toBeNull()
    },
  )

  it('marks legacy duties and shows the Art. 111(2) sentence with the per-copy caveat (item 24)', async () => {
    await openResult(legacyMarked())
    const summary = screen.getByRole('region', { name: 'Result' })
    const note = within(summary).getByRole('note')
    expect(note).toHaveTextContent(
      'Art. 111(2): the tool was on the market or in use before 2 December 2027, so the marked high-risk duties apply only if its design or intended purpose changes significantly.',
    )
    expect(note).toHaveTextContent('apply from 2 August 2030')
    expect(note).toHaveTextContent('This covers copies placed on the market')
    const todo = screen.getByRole('region', { name: 'What you need to do' })
    expect(within(todo).getByText('Only after a significant change')).toBeInTheDocument()
    expect(within(todo).getByText('From 2 August 2030')).toBeInTheDocument()
    expect(within(todo).getAllByText('Art. 111(2)')).toHaveLength(2)
  })

  it("marks a deployer's legacy duties without the per-copy caveat (item 24)", async () => {
    await openResult(legacyMarkedDeployer())
    const note = within(screen.getByRole('region', { name: 'Result' })).getByRole('note')
    expect(note).toHaveTextContent(
      'Art. 111(2): the tool was on the market or in use before 2 December 2027',
    )
    expect(note).not.toHaveTextContent('This covers copies')
    expect(
      within(todoList('en')).getAllByText('Only after a significant change').length,
    ).toBeGreaterThan(0)
  })

  it.each([
    ['en', 'Result', 'apply from 2 August 2030', 'This covers copies placed on the market'],
    ['de', 'Ergebnis', 'ab dem 2. August 2030', 'Das gilt für Exemplare'],
  ] as const)(
    'words the Art. 111(2) note without a route date when every duty moved to 2030 (%s)',
    async (language, region, deadline, perCopy) => {
      await openResult(legacyForPublicAuthorities(), { language })
      const note = within(screen.getByRole('region', { name: region })).getByRole('note')
      expect(note).toHaveTextContent(deadline)
      expect(note).toHaveTextContent(perCopy)
      expect(note).not.toHaveTextContent(/\{\{|2027|2028/)
    },
  )

  it('takes the date duties apply from from the duties the engine dated', async () => {
    const result = decidedHighRisk()
    const moved = (result.obligations ?? []).map((obligation) =>
      obligation.high_risk_route ? { ...obligation, applies_from: '2028-03-01' } : obligation,
    )
    await openResult({ ...result, obligations: moved })
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('1 March 2028')).toBeInTheDocument()
    expect(within(summary).queryByText('2 December 2027')).toBeNull()
  })

  it('renders in German with the German notice', async () => {
    await openResult(decidedHighRisk(), { language: 'de' })
    const summary = screen.getByRole('region', { name: 'Ergebnis' })
    expect(within(summary).getByText('Hochrisiko')).toBeInTheDocument()
    expect(summary).toHaveTextContent('Sie sind Betreiber.')
    expect(summary).toHaveTextContent('Anhang III Nr. 4 Buchst. a')
    expect(within(summary).getByText('2. Dezember 2027')).toBeInTheDocument()
    expect(screen.getByText(NOTICE_DE)).toBeVisible()
  })
})

describe('Result not in this session', () => {
  it('says so and leads to Classify', async () => {
    renderRoute('/app/inventory/unknown-tool')
    expect(await screen.findByRole('heading', { level: 1, name: 'Result' })).toBeInTheDocument()
    expect(screen.getByText(/This result isn't in this session/)).toBeVisible()
  })
})
