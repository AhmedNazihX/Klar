// What the end-to-end flows share (story P13): the runs the API replays, the steps every flow
// starts with, and the checks only a real browser can make (colour contrast, sideways scrolling,
// motion). Every wait is for an element or a response, never for time.
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'

import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'
import type { AxeResults, Result } from 'axe-core'

import runsFile from './runs.json' with { type: 'json' }

/** INIT's worked example, as typed into the form: the API replays E10's recording of it. */
export const WORKED_EXAMPLE = runsFile.workedExample
export const TOOL_NAME = 'Applicant ranking'
export const COMPANY_NAME = 'Nordhafen Logistik'

export type RunName = keyof typeof runsFile.runs
/** The other runs the flows make, each the exact body the app sends (and the backend records). */
export const RUNS = runsFile.runs

const RECORDINGS = path.resolve(
  import.meta.dirname,
  '../../backend/tests/recordings/e2e/test_e2e_runs',
)
const RECORD_COMMAND = 'cd backend && uv run pytest tests/e2e/test_e2e_runs.py --record-mode=once'

/** Whether the API has a recording for `name` (its model cassette and its corpus answers). */
function isRecorded(name: RunName): boolean {
  return ['.yaml', '.corpus.json'].every((suffix) =>
    existsSync(path.join(RECORDINGS, `${name}${suffix}`)),
  )
}

function recordingPending(name: RunName): string {
  return `recording pending: the API has no recording of ${name} yet; record it with \`${RECORD_COMMAND}\``
}

/** The run's request failed because the API had no recording for it (an `error` event). */
class RecordingPendingError extends Error {}

/**
 * Where a flow on `name` meets its run's outcome. Recorded, it returns and the flow goes on.
 * Unrecorded, the run must have stopped for want of its recording (`stopped` shows); the flow then
 * ends here as an expected failure. It is marked expected only now, so any failure before this
 * point, or a run that didn't stop, fails the test for real.
 */
export async function endIfRecordingPending(name: RunName, stopped: Locator): Promise<void> {
  if (isRecorded(name)) return
  await expect(stopped, 'an unrecorded run stops').toBeVisible()
  test.fail(true, recordingPending(name))
  throw new RecordingPendingError(recordingPending(name))
}

// --- Steps --------------------------------------------------------------------------------------

/** The first visit's company profile (Welcome): a small company established and working in the
 *  EU. Lands on the Classify screen. */
export async function saveProfile(page: Page): Promise<void> {
  await page.goto('/app')
  await expect(page).toHaveURL(/\/app\/welcome$/)
  await page.getByRole('textbox', { name: 'Company name' }).fill(COMPANY_NAME)
  await page.getByRole('button', { name: '10–49' }).click()
  await page.getByRole('button', { name: 'Up to €10 m' }).click()
  await page.getByRole('combobox', { name: 'Where you are established' }).selectOption('Germany')
  await page.getByRole('button', { name: 'In the EU' }).click()
  await page.getByRole('button', { name: 'Save and add a tool' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Describe the tool' })).toBeVisible()
}

/** Classifies `description` as a tool named `name` from the Classify screen, and waits for the
 *  saved tool's result. */
export async function classify(page: Page, name: string, description: string): Promise<void> {
  await page.getByRole('textbox', { name: 'What do you call the tool?' }).fill(name)
  await page.getByRole('textbox', { name: 'In your own words' }).fill(description)
  await page.getByRole('button', { name: 'Run the checks' }).click()
  await expectResult(page, name)
}

/** A saved tool's result screen, titled `name`. */
export async function expectResult(page: Page, name: string): Promise<void> {
  await expect(page).toHaveURL(/\/app\/inventory\/[0-9a-f-]{36}/)
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
}

/** A fresh visitor with a profile and the worked example classified: its result is open. */
export async function workedExampleResult(page: Page): Promise<void> {
  await saveProfile(page)
  await classify(page, TOOL_NAME, WORKED_EXAMPLE)
}

const MAX_TABS = 15

/** Presses Tab until `target` has the focus, as a keyboard user would (at most `MAX_TABS` times). */
export async function tabTo(page: Page, target: Locator): Promise<void> {
  for (let tabs = 0; tabs < MAX_TABS; tabs++) {
    if (await target.evaluate((element) => element === document.activeElement)) return
    await page.keyboard.press('Tab')
  }
}

// --- Browser-only checks ------------------------------------------------------------------------

const DESKTOP = { width: 1280, height: 900 }
const PHONE = { width: 375, height: 812 }

/** Attaches screenshots of the page at 1280 px and 375 px to the report (frontend-testing rule:
 *  key screens at both widths), then restores the desktop width. */
export async function attachScreens(page: Page, testInfo: TestInfo, label: string): Promise<void> {
  for (const [width, size] of [
    ['1280', DESKTOP],
    ['375', PHONE],
  ] as const) {
    await page.setViewportSize(size)
    await expect(page.locator('main')).toBeVisible()
    await testInfo.attach(`${label} at ${width} px`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
  }
  await page.setViewportSize(DESKTOP)
}

/** The page fits its viewport's width: nothing scrolls sideways. */
export async function expectNoSidewaysScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow, 'the page scrolls sideways').toBeLessThanOrEqual(0)
}

const AXE_SOURCE = createRequire(import.meta.url).resolve('axe-core/axe.min.js')

type AxeWindow = { axe: { run: (context: Document, options: object) => Promise<AxeResults> } }

/** axe's colour-contrast rule on the page as painted (jsdom can't paint, so the Vitest axe
 *  checks leave it off). Each violation as "<rule>: <element> (<summary>)". */
export async function contrastViolations(page: Page): Promise<string[]> {
  // A screen fades in on load (use-load-motion): measured mid-fade, its text is paler than it
  // ends up. Wait for every motion that ends; the ambient ones (the mist's lights) never do.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity)
      .every((animation) => animation.playState !== 'running'),
  )
  await page.addScriptTag({ path: AXE_SOURCE })
  const results = await page.evaluate(() =>
    (window as unknown as AxeWindow).axe.run(document, { runOnly: ['color-contrast'] }),
  )
  return results.violations.flatMap((violation: Result) =>
    violation.nodes.map(
      (node) => `${violation.id}: ${node.target.join(' ')} (${node.failureSummary ?? ''})`,
    ),
  )
}

/** The CSS animations and transitions still running on the page. */
export async function runningAnimations(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    document
      .getAnimations()
      .filter((animation) => animation.playState === 'running')
      .map((animation) => {
        const target = (animation.effect as KeyframeEffect | null)?.target
        return `${animation.constructor.name} on ${target?.tagName ?? '?'}.${target?.className ?? ''}`
      }),
  )
}
