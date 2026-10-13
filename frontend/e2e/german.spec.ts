// The main flow in German (decision 026, story P11): the app's own words switch with the language,
// and a German description is classified in German.
import { expect, test, type Page } from '@playwright/test'

import {
  RUNS,
  type RunName,
  endIfRecordingPending,
  expectResult,
  saveProfile,
  workedExampleResult,
} from './app.ts'

const GERMAN = RUNS.worked_example_de
const GERMAN_TOOL = 'Bewerber-Ranking'
const DISCLOSURE = 'Orientierungshilfe, keine Rechtsberatung. Klar ist ein KI-System.'
const NO_RECORDING = 'Angehalten: Diese Prüfung konnte nicht abgeschlossen werden.'

test('a result switched to German shows the law switch, pills and duty conditions in German', async ({
  page,
}) => {
  await workedExampleResult(page)
  await page
    .getByRole('group', { name: 'Language' })
    .getByRole('button', { name: 'Deutsch' })
    .click()

  await expect(page.getByRole('group', { name: 'Rechtsstand' }).first()).toBeVisible()
  await expect(
    page
      .getByRole('group', { name: 'Rechtsstand' })
      .first()
      .getByRole('button', { name: 'Geändert, 27.07.2026' }),
  ).toHaveAttribute('aria-pressed', 'true')
  const result = page.getByRole('region', { name: 'Ergebnis', exact: true })
  await expect(result).toContainText('Hochrisiko')
  await expect(result).toContainText('Weitere Angaben nötig')
  // The duties' conditions come from the obligations table's German texts (C9).
  await expect(page.getByText(/^Nur wenn: /).first()).toBeVisible()
  await expect(page.getByText(DISCLOSURE).first()).toBeVisible()
})

test('a German description is classified in German', async ({ page }) => {
  await saveProfile(page)
  await page
    .getByRole('group', { name: 'Language' })
    .getByRole('button', { name: 'Deutsch' })
    .click()
  await page.getByRole('textbox', { name: 'Wie nennen Sie das Tool?' }).fill(GERMAN_TOOL)
  await page.getByRole('textbox', { name: 'In Ihren eigenen Worten' }).fill(GERMAN.description)
  await page.getByRole('button', { name: 'Prüfungen starten' }).click()

  const stopped = page.getByRole('alert').filter({ hasText: NO_RECORDING })
  await expect(page.getByRole('heading', { level: 1, name: GERMAN_TOOL }).or(stopped)).toBeVisible()
  await endIfRecordingPending('worked_example_de', stopped)
  await expectResult(page, GERMAN_TOOL)

  const result = page.getByRole('region', { name: 'Ergebnis', exact: true })
  await expect(result).toContainText('Hochrisiko')
  await expect(page.getByText(/^Nur wenn: /).first()).toBeVisible()
  // The steps quote the German text, in German quotation marks.
  await page.getByRole('button', { name: /Alle Schritte/ }).click()
  await expect(page.getByText(/„[^“]+“/).first()).toBeVisible()
  // A quote inside the quote (Art. 3 Nr. 1 defines „KI-System“) takes the nested marks (P31).
  for (const toggle of await page.getByRole('button', { name: /^Vorschrift(en)? zeigen$/ }).all()) {
    await toggle.click()
  }
  await expect(page.getByText(/^„‚KI-System‘ ein maschinengestütztes System/).first()).toBeVisible()
})

const BANNED = RUNS.prohibited_de
const BANNED_TOOL = 'Stimmungskamera'

/** Classifies the German ban from the Classify screen, in German, and opens its result. */
async function classifyBan(page: Page): Promise<void> {
  await saveProfile(page)
  await page
    .getByRole('group', { name: 'Language' })
    .getByRole('button', { name: 'Deutsch' })
    .click()
  await page.getByRole('textbox', { name: 'Wie nennen Sie das Tool?' }).fill(BANNED_TOOL)
  await page.getByRole('textbox', { name: 'In Ihren eigenen Worten' }).fill(BANNED.description)
  await page.getByRole('button', { name: 'Prüfungen starten' }).click()

  const stopped = page.getByRole('alert').filter({ hasText: NO_RECORDING })
  await expect(page.getByRole('heading', { level: 1, name: BANNED_TOOL }).or(stopped)).toBeVisible()
  await endIfRecordingPending('prohibited_de', stopped)
  await expectResult(page, BANNED_TOOL)
}

test('a German ban is decided, and named in plain words in both languages', async ({ page }) => {
  await classifyBan(page)

  const result = page.getByRole('region', { name: 'Ergebnis', exact: true })
  await expect(result).toContainText('Verboten')
  await expect(result).toContainText('Festgestellt')
  await expect(result).toContainText(
    'Emotionserkennung am Arbeitsplatz oder in Bildungseinrichtungen (Art. 5 Abs. 1 Buchst. f)',
  )

  await page
    .getByRole('group', { name: 'Sprache' })
    .getByRole('button', { name: 'English' })
    .click()
  const english = page.getByRole('region', { name: 'Result', exact: true })
  await expect(english).toContainText('Decided')
  await expect(english).toContainText(
    'recognising emotions in the workplace or in education (Art. 5(1)(f))',
  )
})

/** The re-run a Confirm on the ban makes (P13 note 4d): the exact body the app sends once the user
 *  confirms the first fact the recorded ban assumed. Its answer is the recorded ban's own fact, so
 *  it is added to runs.json only after prohibited_de is recorded; until then this flow says what
 *  to add (the body it sent) and ends as an expected failure. */
const CONFIRMED_RUN = 'prohibited_de_confirmed'
const CONFIRMED = (RUNS as Record<string, unknown>)[CONFIRMED_RUN]

test('a Confirm on the ban runs the checks again, and Undo brings the ban back', async ({
  page,
}, testInfo) => {
  await classifyBan(page)
  const facts = page.getByRole('complementary', { name: 'Das Ergebnis beruht auf' })
  const confirm = facts.getByRole('button', { name: 'Bestätigen' }).first()
  await expect(confirm, 'the recorded ban rests on an assumed fact to confirm').toBeVisible()
  const request = page.waitForRequest((sent) => sent.url().endsWith('/classify'))
  await confirm.click()
  const body: unknown = (await request).postDataJSON()
  if (CONFIRMED === undefined) {
    testInfo.annotations.push({ type: 'add to runs.json', description: JSON.stringify(body) })
    test.fail(true, `add this body to frontend/e2e/runs.json as ${CONFIRMED_RUN}, then record it`)
    throw new Error(`${CONFIRMED_RUN} is not in runs.json yet: ${JSON.stringify(body)}`)
  }
  // The body the backend's e2e recording was made from: a change here means the recording no
  // longer answers the app's request.
  expect(body).toEqual(CONFIRMED)

  const banner = page.getByText(
    /^Ihre Antwort hat (das Ergebnis geändert|die Einstufung nicht geändert)\.$/,
  )
  const stopped = page.getByRole('alert').filter({ hasText: NO_RECORDING })
  await expect(banner.or(stopped)).toBeVisible()
  await endIfRecordingPending(CONFIRMED_RUN as RunName, stopped)
  await expect(page.getByText('Durchlauf 2 von 2')).toBeVisible()

  await page.getByRole('button', { name: 'Antwort rückgängig machen' }).click()
  await expect(banner).toBeHidden()
  await expectResult(page, BANNED_TOOL)
  const result = page.getByRole('region', { name: 'Ergebnis', exact: true })
  await expect(result).toContainText('Verboten')
  await expect(page.getByRole('region', { name: 'Warum die Prüfung endete' })).toBeVisible()
})
