// The follow-up questions the company profile answers (story P29, decision 026 items 2 and 7):
// they leave the open questions and their count, show under "From your company profile" with
// the answer and Change, and are sent when the user runs the checks again. The profile is put in
// the query cache, as Supabase would return it (it isn't configured in the tests).
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult, ClassifyRequest, FollowUpQuestion } from '@/api'
import { userDataOverviewKey } from '@/hooks/use-user-data-overview'
import { RECORDED_AMBIGUOUS, requestHandlers, SAFETY_QUESTION } from '@/test/ambiguous-fixtures'
import type { CompanyProfile, UserDataOverview } from '@/lib/company-profile'
import {
  annexIIINeedsInfo,
  classifyHandler,
  decidedHighRisk,
  WORKED_EXAMPLE_DESCRIPTION,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun } from './classification-store'

const TOOL_ID = 'applicant-screening'
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

const EU_QUESTION: FollowUpQuestion = {
  id: 'eu_link',
  text: 'Is the system placed on the market or used in the EU?',
  hint: 'Decides whether the Act applies. Art. 2(1)',
  options: ['yes', 'no', 'not_sure'],
}
const LEGACY_QUESTION: FollowUpQuestion = {
  id: 'significant_design_change',
  text: "Is a significant change to the system's design or intended purpose planned or foreseen?",
  options: ['yes', 'no', 'not_sure'],
}

const PROFILE: CompanyProfile = {
  companyName: 'Duval',
  staffBand: '10-49',
  turnoverBand: 'up_to_10m',
  establishedIn: null,
  usedIn: 'eu',
  sizeClass: 'sme',
}

function withQuestions(questions: FollowUpQuestion[]): ClassificationResult {
  return { ...decidedHighRisk(), follow_up_questions: questions }
}

/** Streams `result` for every classify request, and keeps each request's body. */
function rerunReturns(result: ClassificationResult): ClassifyRequest[] {
  const bodies: ClassifyRequest[] = []
  server.use(
    classifyHandler(
      [...WORKED_EXAMPLE_EVENTS.slice(0, -1), { event: 'result', result }],
      (body) => {
        bodies.push(body as ClassifyRequest)
      },
    ),
  )
  return bodies
}

function overview(profile: CompanyProfile | null): UserDataOverview {
  return { inventoryId: 'inventory-1', profile, toolCount: 1 }
}

/** The result screen, with the profile read already (`undefined`: not read yet). */
async function openResult(
  result: ClassificationResult,
  profile: CompanyProfile | null | undefined,
  language: 'en' | 'de' = 'en',
) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  if (profile !== undefined) client.setQueryData(userDataOverviewKey, overview(profile))
  putRun(client, {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
  })
  const { container } = renderRoute(`/app/inventory/${TOOL_ID}`, client)
  await screen.findByRole('heading', { level: 1, name: 'Applicant screening' })
  return { user: userEvent.setup(), container, client }
}

function profileRegion(name = 'From your company profile'): HTMLElement {
  return screen.getByRole('region', { name })
}

describe('A question the company profile answers', () => {
  it('leaves the open questions and their count, and shows the answer from the profile', async () => {
    const { container } = await openResult(withQuestions([EU_QUESTION, LEGACY_QUESTION]), PROFILE)

    const open = screen.getByRole('region', { name: '1 open question' })
    expect(open).not.toHaveTextContent(EU_QUESTION.text)
    expect(within(open).getByRole('group', { name: LEGACY_QUESTION.text })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: EU_QUESTION.text })).toBeNull()

    const fromProfile = profileRegion()
    expect(fromProfile).toHaveTextContent(
      'Your company profile answers this question. Klar sends the answer with yours when you run the checks again.',
    )
    expect(fromProfile).toHaveTextContent(EU_QUESTION.text)
    expect(within(fromProfile).getByText('Yes')).toBeVisible()
    expect(within(fromProfile).getByRole('button', { name: 'Change' })).toBeEnabled()
    // One run action, under the last panel, for both questions.
    expect(screen.getAllByRole('button', { name: /run again/ })).toHaveLength(1)
    expect(
      within(fromProfile).getByRole('button', { name: 'Add answers and run again' }),
    ).toBeEnabled()
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])
  })

  it('sends the profile answer with the others when the checks run again', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const { user } = await openResult(withQuestions([EU_QUESTION, LEGACY_QUESTION]), PROFILE)
    const open = screen.getByRole('region', { name: '1 open question' })
    await user.click(
      within(within(open).getByRole('group', { name: LEGACY_QUESTION.text })).getByRole('button', {
        name: 'No',
      }),
    )
    await user.click(
      within(profileRegion()).getByRole('button', { name: 'Add answers and run again' }),
    )

    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({
      eu_link: `${EU_QUESTION.text} Yes.`,
      significant_design_change: `${LEGACY_QUESTION.text} No.`,
    })
  })

  it('sends the profile answer alone when it is the only question', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const { user } = await openResult(withQuestions([EU_QUESTION]), PROFILE)
    expect(screen.queryByRole('region', { name: /open question/ })).toBeNull()

    await user.click(
      within(profileRegion()).getByRole('button', { name: 'Add answer and run again' }),
    )
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({ eu_link: `${EU_QUESTION.text} Yes.` })
  })

  it('Change brings it back as an open question, with nothing pre-selected', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const { user } = await openResult(withQuestions([EU_QUESTION, LEGACY_QUESTION]), PROFILE)
    await user.click(within(profileRegion()).getByRole('button', { name: 'Change' }))

    expect(screen.queryByRole('region', { name: 'From your company profile' })).toBeNull()
    const open = screen.getByRole('region', { name: '2 open questions' })
    const eu = within(open).getByRole('group', { name: EU_QUESTION.text })
    for (const button of within(eu).getAllByRole('button')) {
      expect(button).toHaveAttribute('aria-pressed', 'false')
    }
    const runAgain = within(open).getByRole('button', { name: 'Add answers and run again' })
    expect(runAgain).toBeDisabled()

    // The user's own answer is what goes now.
    await user.click(within(eu).getByRole('button', { name: 'No' }))
    await user.click(runAgain)
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({ eu_link: `${EU_QUESTION.text} No.` })
  })

  it('takes the question that decides a paused result out too, and Change brings it back', async () => {
    const base = annexIIINeedsInfo()
    const deciding = EU_QUESTION
    const result: ClassificationResult = {
      ...base,
      follow_up_questions: [deciding],
      steps: base.steps.map((step) =>
        step.step === 'high_risk' ? { ...step, missing_fact: deciding } : step,
      ),
    }
    const { user } = await openResult(result, PROFILE)
    expect(screen.queryByRole('region', { name: EU_QUESTION.text })).toBeNull()
    expect(profileRegion()).toHaveTextContent(EU_QUESTION.text)
    await user.click(within(profileRegion()).getByRole('button', { name: 'Change' }))
    expect(screen.getByRole('region', { name: EU_QUESTION.text })).toBeInTheDocument()
  })
})

describe('A question the profile does not settle', () => {
  it.each([
    ['no profile', null],
    [
      'a profile established outside the EU, with no place of use',
      { ...PROFILE, establishedIn: 'US', usedIn: null },
    ],
  ] as const)('stays open with nothing pre-selected (%s)', async (_label, profile) => {
    await openResult(withQuestions([EU_QUESTION, LEGACY_QUESTION]), profile)
    expect(screen.queryByRole('region', { name: 'From your company profile' })).toBeNull()
    const open = screen.getByRole('region', { name: '2 open questions' })
    const eu = within(open).getByRole('group', { name: EU_QUESTION.text })
    for (const button of within(eu).getAllByRole('button')) {
      expect(button).toHaveAttribute('aria-pressed', 'false')
    }
    expect(within(open).getByRole('button', { name: 'Add answers and run again' })).toBeDisabled()
  })

  it('takes a profile established in an EU country as an EU link', async () => {
    await openResult(withQuestions([EU_QUESTION]), {
      ...PROFILE,
      establishedIn: 'DE',
      usedIn: null,
    })
    expect(profileRegion()).toHaveTextContent(EU_QUESTION.text)
  })
})

describe('From your company profile, in German', () => {
  it('shows the German line and sends the German answer', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const { user } = await openResult(withQuestions([EU_QUESTION, LEGACY_QUESTION]), PROFILE, 'de')
    expect(screen.getByRole('region', { name: '1 offene Frage' })).not.toHaveTextContent(
      EU_QUESTION.text,
    )
    const fromProfile = profileRegion('Aus Ihrem Unternehmensprofil')
    expect(fromProfile).toHaveTextContent(
      'Ihr Unternehmensprofil beantwortet diese Frage. Klar sendet die Antwort mit Ihren Antworten, wenn Sie die Prüfungen erneut starten.',
    )
    expect(within(fromProfile).getByText('Ja')).toBeVisible()
    expect(within(fromProfile).getByRole('button', { name: 'Ändern' })).toBeEnabled()

    await user.click(
      within(fromProfile).getByRole('button', { name: 'Antworten hinzufügen und erneut prüfen' }),
    )
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({ eu_link: `${EU_QUESTION.text} Ja.` })
  })
})

describe('An answer given before the profile is read', () => {
  it('stays the user’s: the profile read later never replaces it', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const { user, client } = await openResult(
      withQuestions([EU_QUESTION, LEGACY_QUESTION]),
      undefined,
    )
    const open = screen.getByRole('region', { name: '2 open questions' })
    const eu = within(open).getByRole('group', { name: EU_QUESTION.text })
    await user.click(within(eu).getByRole('button', { name: 'No' }))

    act(() => {
      client.setQueryData(
        userDataOverviewKey,
        overview({ ...PROFILE, establishedIn: 'DE', usedIn: null }),
      )
    })
    expect(screen.queryByRole('region', { name: 'From your company profile' })).toBeNull()
    expect(within(eu).getByRole('button', { name: 'No' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(within(open).getByRole('button', { name: 'Add answers and run again' }))
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({ eu_link: `${EU_QUESTION.text} No.` })
  })
})

describe('A legally ambiguous result with a question the profile answers', () => {
  it('shows the profile answer with the one run action, and sends it', async () => {
    server.use(...requestHandlers([]))
    const bodies = rerunReturns(RECORDED_AMBIGUOUS)
    const result: ClassificationResult = {
      ...RECORDED_AMBIGUOUS,
      follow_up_questions: [SAFETY_QUESTION, EU_QUESTION],
    }
    const { user } = await openResult(result, PROFILE)

    const fromProfile = profileRegion()
    expect(fromProfile).toHaveTextContent(EU_QUESTION.text)
    expect(screen.queryByRole('group', { name: EU_QUESTION.text })).toBeNull()
    expect(screen.getAllByRole('button', { name: /run again/ })).toHaveLength(1)

    await user.click(within(fromProfile).getByRole('button', { name: 'Add answers and run again' }))
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({ eu_link: `${EU_QUESTION.text} Yes.` })
  })
})
