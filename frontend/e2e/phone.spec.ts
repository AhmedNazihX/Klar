// One result at 390 px (decision 026, story P26): the whole flow on a phone's width, with nothing
// scrolling sideways on Welcome, Classify or the result, and the result's own law switch.
import { expect, test } from '@playwright/test'

import { TOOL_NAME, WORKED_EXAMPLE, classify, expectNoSidewaysScroll, saveProfile } from './app.ts'

test.use({ viewport: { width: 390, height: 844 } })

test('the worked example’s result fits a 390 px phone', async ({ page }, testInfo) => {
  await page.goto('/app')
  await expect(
    page.getByRole('heading', { level: 1, name: "Let's see where your AI tools stand." }),
  ).toBeVisible()
  await expectNoSidewaysScroll(page)

  await saveProfile(page)
  await expectNoSidewaysScroll(page)
  await classify(page, TOOL_NAME, WORKED_EXAMPLE)

  await expect(page.getByRole('region', { name: 'Result', exact: true })).toContainText('High-risk')
  await expect(page.getByRole('group', { name: 'Law version' }).first()).toBeVisible()
  await expectNoSidewaysScroll(page)
  await testInfo.attach('result at 390 px', {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
})
