// What a classified tool leads to (stories P9, P24, P25): a duty ticked off on Obligations and kept
// across a reload, the checklist and the result's report as PDF, and one draft document answered
// and downloaded. The files are rendered by the API itself; nothing is replayed for them.
import { expect, test } from '@playwright/test'

import { TOOL_NAME, workedExampleResult } from './app.ts'
import { download, expectDocx, expectPdf } from './files.ts'

const DUTY = "Use the tool as the vendor's instructions say"
const OVERSIGHT_ANSWER = 'The head of HR and one trained recruiter'

test('a duty ticked on Obligations stays ticked, and the checklist downloads', async ({ page }) => {
  await workedExampleResult(page)
  await page
    .getByRole('navigation', { name: 'App' })
    .getByRole('link', { name: 'Obligations' })
    .click()
  await expect(page.getByRole('heading', { level: 1, name: 'Obligations' })).toBeVisible()
  const progress = page.getByRole('region', { name: 'Progress' })
  await expect(progress).toContainText('0 of 11 done')

  const duty = page.getByRole('checkbox', { name: DUTY })
  // The tick shows once Supabase has saved it (duty_progress), so click and wait for it.
  await duty.click()
  await expect(duty).toBeChecked()
  await expect(progress).toContainText('1 of 11 done')

  await page.reload()
  await expect(page.getByRole('checkbox', { name: DUTY })).toBeChecked()
  await expect(page.getByRole('region', { name: 'Progress' })).toContainText('1 of 11 done')

  const checklist = page.getByRole('region', { name: 'Take the checklist with you' })
  await expectPdf(await download(page, checklist.getByRole('button', { name: 'Download PDF' })), [
    TOOL_NAME,
    DUTY,
  ])
})

test('the result’s report downloads as a PDF', async ({ page }) => {
  await workedExampleResult(page)
  await expectPdf(await download(page, page.getByRole('button', { name: 'Export PDF' })), [
    TOOL_NAME,
    'High-risk',
    'Annex III',
  ])
})

test('a draft document takes an answer and downloads as PDF and Word', async ({ page }) => {
  await workedExampleResult(page)
  await page.getByRole('link', { name: 'Draft documents' }).click()
  await expect(page.getByRole('region', { name: `For ${TOOL_NAME}` })).toBeVisible()
  const preview = page.getByRole('article', { name: 'Document preview' })
  await expect(
    preview.getByRole('heading', { level: 1, name: 'Human oversight record' }),
  ).toBeVisible()
  await expect(page.getByRole('region', { name: 'Automatic checks' })).toContainText(
    'Every required section is present',
  )

  const interview = page.getByRole('region', { name: 'Guided interview' })
  await expect(interview).toContainText('0 of 3 answered')
  await interview
    .getByRole('textbox', { name: 'Who is assigned to oversee the system? Give names or roles.' })
    .fill(OVERSIGHT_ANSWER)
  await interview.getByRole('button', { name: 'Save answer' }).click()
  await expect(interview).toContainText('1 of 3 answered')
  await expect(preview.getByRole('region', { name: 'Who oversees the system' })).toContainText(
    OVERSIGHT_ANSWER,
  )

  const draft = ['Human oversight record', 'Who oversees the system', OVERSIGHT_ANSWER]
  await expectPdf(await download(page, page.getByRole('button', { name: 'Download PDF' })), draft)
  await expectDocx(
    await download(page, page.getByRole('button', { name: 'Download .docx' })),
    draft,
  )
})
