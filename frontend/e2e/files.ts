// The files the flows download, checked by their first bytes (a PDF starts with `%PDF-`, a Word
// file is a ZIP container, `PK`) and by their text. The text is read back by the backend's own
// test reader (backend/tests/export/reading.py: pypdf and python-docx, already in the backend's
// environment, which the run's API uses), so the e2e tests need no PDF or ZIP library of their own.
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { promisify } from 'node:util'

import { expect, type Download, type Locator, type Page } from '@playwright/test'

const PDF_MAGIC = '%PDF-'
const DOCX_MAGIC = 'PK'

/** A render takes about a second; the API stops one at 10 s (EXPORT_TIMEOUT_SECONDS). */
const DOWNLOAD_TIMEOUT_MS = 15_000

const BACKEND = path.resolve(import.meta.dirname, '../../backend')
/** Prints a PDF's pages, or a Word file's title and paragraphs, one per line. */
const READ_BACK = [
  'import pathlib, sys',
  'from tests.export.reading import pdf_pages, read_docx',
  'kind, data = sys.argv[1], pathlib.Path(sys.argv[2]).read_bytes()',
  'word = read_docx(data) if kind == "docx" else None',
  'print("\\n".join(pdf_pages(data) if word is None else [word.title, *word.paragraphs]))',
].join('\n')

const run = promisify(execFile)

/** Clicks `button` and returns the file the page downloads. */
export async function download(page: Page, button: Locator): Promise<Download> {
  const started = page.waitForEvent('download', { timeout: DOWNLOAD_TIMEOUT_MS })
  await button.click()
  return started
}

async function firstBytes(file: Download, count: number): Promise<string> {
  const bytes = await readFile(await file.path())
  return bytes.subarray(0, count).toString('latin1')
}

async function textOf(kind: 'pdf' | 'docx', file: Download): Promise<string> {
  const args = ['run', '--directory', BACKEND, 'python', '-c', READ_BACK, kind, await file.path()]
  const { stdout } = await run('uv', args, { encoding: 'utf8' })
  return stdout
}

async function expectTexts(kind: 'pdf' | 'docx', file: Download, texts: readonly string[]) {
  const text = await textOf(kind, file)
  for (const expected of texts) expect(text, `the ${kind}'s text`).toContain(expected)
}

/** A PDF whose text holds each of `texts`. */
export async function expectPdf(file: Download, texts: readonly string[]): Promise<void> {
  expect(file.suggestedFilename()).toMatch(/\.pdf$/)
  expect(await firstBytes(file, PDF_MAGIC.length)).toBe(PDF_MAGIC)
  await expectTexts('pdf', file, texts)
}

/** A Word file whose title and paragraphs hold each of `texts`. */
export async function expectDocx(file: Download, texts: readonly string[]): Promise<void> {
  expect(file.suggestedFilename()).toMatch(/\.docx$/)
  expect(await firstBytes(file, DOCX_MAGIC.length)).toBe(DOCX_MAGIC)
  await expectTexts('docx', file, texts)
}
