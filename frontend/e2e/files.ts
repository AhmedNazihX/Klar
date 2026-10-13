// The files the flows download, checked by their first bytes: a PDF starts with `%PDF-`, a Word
// file is a ZIP container (`PK`).
import { readFile } from 'node:fs/promises'

import { expect, type Download, type Locator, type Page } from '@playwright/test'

const PDF_MAGIC = '%PDF-'
const DOCX_MAGIC = 'PK'

/** A render takes about a second; the API stops one at 10 s (EXPORT_TIMEOUT_SECONDS). */
const DOWNLOAD_TIMEOUT_MS = 15_000

/** Clicks `button` and returns the file the page downloads. */
export async function download(page: Page, button: Locator): Promise<Download> {
  const started = page.waitForEvent('download', { timeout: DOWNLOAD_TIMEOUT_MS })
  await button.click()
  return started
}

async function firstBytes(file: Download, count: number): Promise<string> {
  const filePath = await file.path()
  const bytes = await readFile(filePath)
  return bytes.subarray(0, count).toString('latin1')
}

export async function expectPdf(file: Download): Promise<void> {
  expect(file.suggestedFilename()).toMatch(/\.pdf$/)
  expect(await firstBytes(file, PDF_MAGIC.length)).toBe(PDF_MAGIC)
}

export async function expectDocx(file: Download): Promise<void> {
  expect(file.suggestedFilename()).toMatch(/\.docx$/)
  expect(await firstBytes(file, DOCX_MAGIC.length)).toBe(DOCX_MAGIC)
}
