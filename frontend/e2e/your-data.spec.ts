// Delete my data (story P12): the counts of what Klar keeps, a confirm that asks for DELETE typed
// out, and a fresh, empty session afterwards.
import { expect, test } from '@playwright/test'

import { workedExampleResult } from './app.ts'

test('delete my data asks for DELETE, then deletes everything and ends the session', async ({
  page,
}) => {
  await workedExampleResult(page)
  await page.getByRole('complementary').getByRole('link', { name: 'Delete my data' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Your data' })).toBeVisible()
  const keeps = page.getByRole('region', { name: 'What Klar keeps' })
  for (const [term, count] of [
    ['Tools and their descriptions', '1'],
    ['Classification results', '1'],
    ['Company profile', '1'],
  ] as const) {
    await expect(keeps.locator(`dt:has-text("${term}") + dd`)).toHaveText(count)
  }

  await page
    .getByRole('region', { name: 'Delete my data' })
    .getByRole('button', { name: 'Delete my data' })
    .click()
  const dialog = page.getByRole('dialog', { name: 'Delete everything?' })
  await expect(dialog).toContainText(
    'Klar will delete 1 tool, 1 result and your company profile for good.',
  )
  const confirm = dialog.getByRole('button', { name: 'Delete everything' })
  const typed = dialog.getByRole('textbox', { name: 'Type DELETE to confirm' })
  await expect(confirm).toBeDisabled()
  await typed.fill('delete')
  await expect(confirm).toBeDisabled()
  await typed.fill('DELETE')
  await expect(confirm).toBeEnabled()
  await confirm.click()

  // A new anonymous session with nothing in it: the first visit again.
  await expect(dialog).toBeHidden()
  await page.goto('/app')
  await expect(page).toHaveURL(/\/app\/welcome$/)
  await expect(page.getByRole('region', { name: 'Your AI tools' })).toContainText('No tools yet')
  await page.goto('/app/your-data')
  for (const term of [
    'Tools and their descriptions',
    'Classification results',
    'Company profile',
  ]) {
    await expect(keeps.locator(`dt:has-text("${term}") + dd`)).toHaveText('0')
  }
})
