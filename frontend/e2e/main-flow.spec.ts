// The main flow (story P13, decision 026): a first visit saves the company profile, classifies
// INIT's worked example from the keyboard, reads its result and finds it in the inventory; a
// returning visit keeps the profile across a real reload.
import { expect, test } from '@playwright/test'

import {
  COMPANY_NAME,
  TOOL_NAME,
  WORKED_EXAMPLE,
  attachScreens,
  expectResult,
  saveProfile,
  tabTo,
  workedExampleResult,
} from './app.ts'

const DISCLOSURE = 'Guidance, not legal advice. Klar is an AI system.'

test('a first visit saves the profile, classifies the worked example and lists it', async ({
  page,
}, testInfo) => {
  await saveProfile(page)
  await expect(page.getByRole('link', { name: new RegExp(COMPANY_NAME) })).toBeVisible()

  // The form from the keyboard: type, then Tab to the run button and press Enter.
  await page.getByRole('textbox', { name: 'What do you call the tool?' }).focus()
  await page.keyboard.type(TOOL_NAME)
  await page.keyboard.press('Tab')
  await expect(page.getByRole('textbox', { name: 'In your own words' })).toBeFocused()
  await page.keyboard.type(WORKED_EXAMPLE)
  const run = page.getByRole('button', { name: 'Run the checks' })
  await tabTo(page, run)
  await expect(run).toBeFocused()
  await page.keyboard.press('Enter')
  await expectResult(page, TOOL_NAME)

  // The recorded result: high-risk under Annex III 4(a), assumed until Art. 3(1) is answered.
  const result = page.getByRole('region', { name: 'Result', exact: true })
  await expect(result).toContainText('High-risk')
  await expect(result).toContainText('Assumed')
  await expect(result).toContainText('Needs more information')
  await expect(
    page.getByText('Checked on 6 October 2026 against the consolidated AI Act of 27 July 2026.'),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { level: 2, name: /How does the system produce its outputs/ }),
  ).toBeVisible()
  // The run button shows before anything is answered (P5b): the loop never hides it.
  await expect(page.getByRole('button', { name: 'Add answers and run again' })).toBeVisible()
  const duties = page.getByRole('region', { name: 'What you need to do' })
  await expect(
    duties.getByRole('checkbox', { name: "Use the tool as the vendor's instructions say" }),
  ).toBeVisible()
  await expect(duties).toContainText('Art. 26(1)')
  await expect(page.getByText(DISCLOSURE).first()).toBeVisible()
  await attachScreens(page, testInfo, 'result')

  await page
    .getByRole('navigation', { name: 'App' })
    .getByRole('link', { name: 'Inventory' })
    .click()
  await expect(page.getByRole('heading', { level: 1, name: 'Your AI tools' })).toBeVisible()
  await expect(
    page.getByText('1 tool, classified under the AI Act as amended on 27 July 2026.'),
  ).toBeVisible()
  const row = page.getByRole('table', { name: 'Your tools and their results' }).getByRole('row', {
    name: new RegExp(TOOL_NAME),
  })
  for (const cell of [
    'Deployer',
    'High-risk, assumed',
    'Annex III 4(a)',
    '2 Dec 2027',
    'Needs more information',
  ]) {
    await expect(row.getByRole('cell', { name: cell, exact: true })).toBeVisible()
  }
  await expect(page.getByRole('heading', { level: 2, name: '1 tool needs you' })).toBeVisible()
  await attachScreens(page, testInfo, 'inventory')
})

test('a returning visit keeps the profile, which answers the EU question after a reload', async ({
  page,
}) => {
  await workedExampleResult(page)
  // A real reload: the profile comes from Supabase, not from a cache the first visit filled.
  await page.reload()
  await expectResult(page, TOOL_NAME)
  const fromProfile = page.getByRole('region', { name: 'From your company profile' })
  const euQuestion =
    'Is the tool placed on the market or used in the EU, or are its outputs used there?'
  await expect(fromProfile.getByText(euQuestion)).toBeVisible()
  await expect(fromProfile.getByText('Yes', { exact: true })).toBeVisible()

  // Change asks it again among the open questions (answered in words, as the recorded question
  // offers no options), with focus on its answer.
  await fromProfile.getByRole('button', { name: 'Change' }).click()
  await expect(fromProfile).toBeHidden()
  await expect(page.getByRole('textbox', { name: euQuestion })).toBeFocused()

  // The app's start sends a returning user to the inventory, not back to Welcome.
  await page.goto('/app')
  await expect(page).toHaveURL(/\/app\/inventory$/)
  await expect(page.getByRole('link', { name: new RegExp(COMPANY_NAME) })).toBeVisible()
})
