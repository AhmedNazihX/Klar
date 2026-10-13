// What only a painted page shows (stories P14, P16, P18): colour contrast on the key screens, which
// the Vitest axe checks leave off (jsdom can't paint), and no motion for a visitor who asks for
// reduced motion.
import { expect, test } from '@playwright/test'

import { contrastViolations, runningAnimations, workedExampleResult } from './app.ts'

test('the landing page and Welcome meet the colour contrast minimum', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  expect(await contrastViolations(page)).toEqual([])

  await page.goto('/app')
  await expect(page.getByRole('region', { name: 'About your company' })).toBeVisible()
  expect(await contrastViolations(page)).toEqual([])
})

test('the app’s screens meet the colour contrast minimum', async ({ page }) => {
  await workedExampleResult(page)
  expect(await contrastViolations(page), 'result').toEqual([])
  for (const [path, heading] of [
    ['/app/classify', 'Describe the tool'],
    ['/app/inventory', 'Your AI tools'],
    ['/app/obligations', 'Obligations'],
    ['/app/your-data', 'Your data'],
  ] as const) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
    expect(await contrastViolations(page), path).toEqual([])
  }
})

test.describe('with reduced motion', () => {
  test.use({ reducedMotion: 'reduce' })

  // Read as soon as each screen shows: without the preference, the landing page's timeline, the
  // segmented controls and the app's load motion are all still running then.
  test('nothing moves on the landing page or in the app', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(await runningAnimations(page), 'landing').toEqual([])

    await workedExampleResult(page)
    expect(await runningAnimations(page), 'result').toEqual([])

    await page
      .getByRole('navigation', { name: 'App' })
      .getByRole('link', { name: 'Inventory' })
      .click()
    await expect(page.getByRole('heading', { level: 1, name: 'Your AI tools' })).toBeVisible()
    expect(await runningAnimations(page), 'inventory').toEqual([])
  })
})
