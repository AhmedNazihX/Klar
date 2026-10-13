// Delete my data (story P12): the counts of what Klar keeps, a confirm that asks for DELETE typed
// out, the user's rows gone from the database, and a fresh, empty session afterwards.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { workedExampleResult } from './app.ts'
import { supabaseStack, type SupabaseStack } from './stack.ts'

/** The tables the flow writes to: the inventory (with the company profile), the tool, its result. */
const USER_TABLES = ['inventories', 'systems', 'classifications'] as const
const SESSION_KEY = /^sb-.+-auth-token$/

type StoredSession = { userId: string; accessToken: string }

/** The anonymous session supabase-js keeps in localStorage (src/lib/supabase.ts). */
async function storedSession(page: Page): Promise<StoredSession> {
  const stored = await page.evaluate((pattern) => {
    const key = Object.keys(localStorage).find((name) => new RegExp(pattern).test(name))
    return key ? localStorage.getItem(key) : null
  }, SESSION_KEY.source)
  expect(stored, 'a stored Supabase session').not.toBeNull()
  const session = JSON.parse(stored ?? '{}') as { access_token: string; user: { id: string } }
  return { userId: session.user.id, accessToken: session.access_token }
}

/** How many rows of each table `accessToken`'s user can read, through the stack's REST API (RLS
 *  keeps it to the user's own rows). */
async function rowCounts(
  request: APIRequestContext,
  { url, anonKey }: SupabaseStack,
  accessToken: string,
): Promise<Record<string, number>> {
  const counts: Record<string, number> = {}
  for (const table of USER_TABLES) {
    const response = await request.get(`${url}/rest/v1/${table}?select=user_id`, {
      headers: { apikey: anonKey, Authorization: `Bearer ${accessToken}` },
    })
    expect(response.status(), table).toBe(200)
    counts[table] = ((await response.json()) as unknown[]).length
  }
  return counts
}

test('delete my data asks for DELETE, then deletes everything and ends the session', async ({
  page,
  request,
}) => {
  const stack = supabaseStack()
  await workedExampleResult(page)
  const before = await storedSession(page)
  // The old session sees its rows: the check after the deletion can only pass by their removal.
  expect(await rowCounts(request, stack, before.accessToken)).toEqual({
    inventories: 1,
    systems: 1,
    classifications: 1,
  })

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
  await expect(dialog).toBeHidden()

  // The old user's rows are gone from the database, read with its own (still unexpired) token.
  expect(await rowCounts(request, stack, before.accessToken)).toEqual({
    inventories: 0,
    systems: 0,
    classifications: 0,
  })

  // A new anonymous session with nothing in it: the first visit again.
  await page.goto('/app')
  await expect(page).toHaveURL(/\/app\/welcome$/)
  await expect(page.getByRole('region', { name: 'Your AI tools' })).toContainText('No tools yet')
  expect((await storedSession(page)).userId, 'the session after the deletion').not.toBe(
    before.userId,
  )
  await page.goto('/app/your-data')
  for (const term of [
    'Tools and their descriptions',
    'Classification results',
    'Company profile',
  ]) {
    await expect(keeps.locator(`dt:has-text("${term}") + dd`)).toHaveText('0')
  }
})
