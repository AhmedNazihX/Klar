// The main flow in German (decision 026, story P11): the app's own words switch with the language,
// and a German description is classified in German.
import { expect, test } from '@playwright/test'

import {
  RUNS,
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
})
