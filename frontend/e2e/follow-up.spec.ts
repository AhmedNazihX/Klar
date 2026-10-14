// The needs-info loop (stories P5b, P29; decision 019): the worked example pauses on its Art. 3(1)
// question; the user answers it and runs the checks again, with the company profile's EU answer
// sent too, then undoes the answer. And (P31) a No to one of its Yes/No questions.
import { expect, test, type Page } from '@playwright/test'

import { RUNS, TOOL_NAME, endIfRecordingPending, expectResult, workedExampleResult } from './app.ts'

const ANSWERED = RUNS.worked_example_answered
const DECIDING_QUESTION = /How does the system produce its outputs/
/** What the progress shows when the API had no recording for the run: its first node stopped,
 *  and the earlier result stands. */
const NO_RECORDING = "Stopped: this check couldn't finish."

async function answerAndRunAgain(page: Page): Promise<void> {
  await page.getByRole('textbox', { name: DECIDING_QUESTION }).fill(ANSWERED.answers.ai_system)
  await page.getByRole('button', { name: /run again/ }).click()
}

test('the re-run sends the answer and the profile’s EU answer, as recorded', async ({ page }) => {
  await workedExampleResult(page)
  const request = page.waitForRequest((sent) => sent.url().endsWith('/classify'))
  await answerAndRunAgain(page)
  // The body the backend's e2e recording was made from (runs.json): a change here means the
  // recording no longer answers the app's request.
  expect((await request).postDataJSON()).toEqual(ANSWERED)
  await (await request).response()
})

const NOT_FOR_AUTHORITIES = RUNS.worked_example_not_for_authorities
const AUTHORITY_QUESTION = 'Is the system meant for use by public authorities?'

async function answerNoAndRunAgain(page: Page): Promise<void> {
  await page
    .getByRole('group', { name: AUTHORITY_QUESTION })
    .getByRole('button', { name: 'No', exact: true })
    .click()
  await page.getByRole('button', { name: /run again/ }).click()
}

test('a No to a Yes/No question is sent as recorded, after the profile’s EU answer', async ({
  page,
}) => {
  await workedExampleResult(page)
  const request = page.waitForRequest((sent) => sent.url().endsWith('/classify'))
  await answerNoAndRunAgain(page)
  const body = (await request).postDataJSON() as typeof NOT_FOR_AUTHORITIES
  expect(body).toEqual(NOT_FOR_AUTHORITIES)
  // In the same order too: the engine reads the answers in the order they come.
  expect(Object.keys(body.answers)).toEqual(Object.keys(NOT_FOR_AUTHORITIES.answers))
  await (await request).response()
})

test('a No re-runs the checks, and the question it answered is not asked again', async ({
  page,
}) => {
  await workedExampleResult(page)
  await answerNoAndRunAgain(page)

  const banner = page.getByText(/^Your answer (changed the result|didn't change the class)\.$/)
  const stopped = page.getByRole('alert').filter({ hasText: NO_RECORDING })
  await expect(banner.or(stopped)).toBeVisible()
  await endIfRecordingPending('worked_example_not_for_authorities', stopped)
  await expect(page.getByText('Run 2 of 2')).toBeVisible()
  await expect(page.getByRole('group', { name: AUTHORITY_QUESTION })).toBeHidden()
})

test('an answer re-runs the checks, and Undo answer brings the paused result back', async ({
  page,
}) => {
  await workedExampleResult(page)
  await answerAndRunAgain(page)

  const banner = page.getByText(/^Your answer (changed the result|didn't change the class)\.$/)
  const stopped = page.getByRole('alert').filter({ hasText: NO_RECORDING })
  await expect(banner.or(stopped)).toBeVisible()
  await endIfRecordingPending('worked_example_answered', stopped)
  await expect(page.getByText('Run 2 of 2')).toBeVisible()
  await expect(page.getByText(ANSWERED.answers.ai_system, { exact: false })).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: DECIDING_QUESTION })).toBeHidden()

  await page.getByRole('button', { name: 'Undo answer' }).click()
  await expect(banner).toBeHidden()
  await expectResult(page, TOOL_NAME)
  await expect(page.getByRole('region', { name: 'Result', exact: true })).toContainText(
    'Needs more information',
  )
  await expect(page.getByRole('heading', { level: 2, name: DECIDING_QUESTION })).toBeVisible()
})
