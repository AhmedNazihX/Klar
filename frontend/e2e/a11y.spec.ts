// What only a painted page shows (stories P14, P16, P18): colour contrast on the key screens, which
// the Vitest axe checks leave off (jsdom can't paint), and no motion for a visitor who asks for
// reduced motion.
import { expect, test } from '@playwright/test'

import {
  TOOL_NAME,
  WORKED_EXAMPLE,
  contrastViolations,
  expectResult,
  runningAnimations,
  saveProfile,
  workedExampleResult,
} from './app.ts'

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
  // segmented controls and the app's load motion are all still running then. Those are started
  // by script only when motion is allowed; the running check's ring (CheckProgress, check-spin)
  // is CSS alone, which only index.css › reduced-motion stops.
  test('nothing moves on the landing page or in the app', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(await runningAnimations(page), 'landing').toEqual([])

    // Hold the run before it reaches the API, so its first check shows as running.
    let release = (): void => {}
    const isReleased = new Promise<void>((resolve) => (release = resolve))
    await page.route(
      (url) => url.pathname === '/classify',
      async (route) => {
        await isReleased
        await route.continue()
      },
    )
    await saveProfile(page)
    await page.getByRole('textbox', { name: 'What do you call the tool?' }).fill(TOOL_NAME)
    await page.getByRole('textbox', { name: 'In your own words' }).fill(WORKED_EXAMPLE)
    await page.getByRole('button', { name: 'Run the checks' }).click()
    await expect(page.locator('.check-ring')).toBeVisible()
    expect(await runningAnimations(page), 'a running check').toEqual([])
    release()
    await expectResult(page, TOOL_NAME)
    expect(await runningAnimations(page), 'result').toEqual([])

    await page
      .getByRole('navigation', { name: 'App' })
      .getByRole('link', { name: 'Inventory' })
      .click()
    await expect(page.getByRole('heading', { level: 1, name: 'Your AI tools' })).toBeVisible()
    expect(await runningAnimations(page), 'inventory').toEqual([])
  })
})
