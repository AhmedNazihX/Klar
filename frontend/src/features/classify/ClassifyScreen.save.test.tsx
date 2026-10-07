// Classify with Supabase configured (P6): a finished run becomes a tool in the inventory. The
// other Classify tests run without Supabase, where nothing is saved.
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  classifyHandler,
  WORKED_EXAMPLE,
  WORKED_EXAMPLE_DESCRIPTION,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { SAVE_TOOL_URL } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import {
  FIRST_RENDER_MS,
  INVENTORY_ID,
  inventoryRow,
  userDataHandlers,
} from '@/test/user-data-handlers'

import { clearDraft, readDraft, saveDraft } from './classification-store'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const SYSTEM_ID = '3b9d2f1e-6a4c-4e0b-8f3a-1c2d3e4f5a6b'

let inventories: Record<string, unknown>[] = []
let saves: unknown[] = []
let classifyRequests = 0

/** Records each save_classified_tool call; it answers with the new tool's id, or fails with
 *  `error`. With `held`, the answer waits until that promise resolves. */
function saveHandler(
  error: { status: number; code: string } | null = null,
  held: Promise<void> = Promise.resolve(),
) {
  return http.post(SAVE_TOOL_URL, async ({ request }) => {
    saves.push(await request.json())
    await held
    return error
      ? HttpResponse.json({ code: error.code, message: 'refused' }, { status: error.status })
      : HttpResponse.json(SYSTEM_ID)
  })
}

beforeEach(() => {
  clearDraft()
  inventories = [inventoryRow()]
  saves = []
  classifyRequests = 0
  server.use(
    ...userDataHandlers(
      () => inventories,
      () => 0,
    ),
    classifyHandler(WORKED_EXAMPLE_EVENTS, () => {
      classifyRequests += 1
    }),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

async function classify(name: string, language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute('/app/classify')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  const labels =
    language === 'de'
      ? { name: 'Wie nennen Sie das Tool?', description: 'In Ihren eigenen Worten' }
      : { name: 'What do you call the tool?', description: 'In your own words' }
  if (name) await user.type(screen.getByLabelText(labels.name), name)
  await user.type(screen.getByLabelText(labels.description), WORKED_EXAMPLE_DESCRIPTION)
  await user.click(
    screen.getByRole('button', {
      name: language === 'de' ? 'Prüfungen starten' : 'Run the checks',
    }),
  )
  return { user, ...rendered }
}

describe('Classify, saving the run to the inventory', () => {
  it('saves the tool and its run in one call and opens the saved tool', async () => {
    server.use(saveHandler())
    const { router } = await classify('Applicant screening')

    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Applicant screening' }),
    ).toBeInTheDocument()
    expect(saves).toEqual([
      {
        target_inventory_id: INVENTORY_ID,
        new_inventory_name: 'AI inventory',
        tool_name: 'Applicant screening',
        tool_description: WORKED_EXAMPLE_DESCRIPTION,
        tool_result: WORKED_EXAMPLE,
        // A run from an empty form is a new tool.
        target_system_id: null,
      },
    ])
    expect(screen.queryByRole('alert')).toBeNull()
    expect(classifyRequests).toBe(1)
  })

  it.each([
    ['en', 'AI inventory', 'Your tool'],
    ['de', 'KI-Inventar', 'Ihr Tool'],
  ] as const)(
    'names a new inventory, and stores an unnamed tool without a name (%s)',
    async (language, inventoryName, shownName) => {
      inventories = []
      server.use(saveHandler())
      await classify('', language)

      await expect.poll(() => saves.length).toBe(1)
      expect(saves[0]).toMatchObject({
        target_inventory_id: null,
        new_inventory_name: inventoryName,
        tool_name: null,
      })
      // The placeholder is shown, in the reader's language, never stored.
      expect(await screen.findByRole('heading', { level: 1, name: shownName })).toBeInTheDocument()
    },
  )

  it('stays busy until the run is saved, so a second click starts no second run', async () => {
    let release = (): void => undefined
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(saveHandler(null, held))
    const { user, router } = await classify('Applicant screening')

    await expect.poll(() => saves.length).toBe(1)
    const button = screen.getByRole('button', { name: 'Checking…' })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(classifyRequests).toBe(1)

    release()
    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
    expect(classifyRequests).toBe(1)
    expect(saves).toHaveLength(1)
  })

  it.each([
    [
      'en',
      'PT507',
      "This result wasn't saved: your data has reached its storage limit. Make room under Your data, then run the checks again.",
    ],
    [
      'de',
      'PT507',
      'Dieses Ergebnis wurde nicht gespeichert: Ihre Daten haben die Speichergrenze erreicht. Schaffen Sie unter „Ihre Daten“ Platz und starten Sie die Prüfungen erneut.',
    ],
    [
      'en',
      'XX000',
      "This result wasn't saved to your inventory. It stays on this page until you reload or leave it.",
    ],
    [
      'de',
      'XX000',
      'Dieses Ergebnis wurde nicht in Ihrem Inventar gespeichert. Es bleibt auf dieser Seite, bis Sie sie neu laden oder verlassen.',
    ],
  ] as const)(
    'still opens a run it could not save, and says so (%s, %s)',
    async (language, code, message) => {
      server.use(saveHandler({ status: 400, code }))
      const { router } = await classify('Applicant screening', language)

      expect(await screen.findByRole('alert', {}, { timeout: FIRST_RENDER_MS })).toHaveTextContent(
        message,
      )
      expect(router.state.location.pathname).toMatch(/^\/app\/inventory\/[\w-]+$/)
      expect(router.state.location.pathname).not.toBe(`/app/inventory/${SYSTEM_ID}`)
      expect(screen.getByRole('heading', { level: 1, name: 'Applicant screening' })).toBeVisible()
      // Nothing is run again: the run was paid for once.
      expect(classifyRequests).toBe(1)
    },
  )
})

describe('Classify, a draft for a tool the user has', () => {
  const OLD_TOOL_ID = '7c1e4b2a-9d3f-4a5e-8b6c-0d1e2f3a4b5c'

  /** "Classify this tool" left this draft: the old tool's name and description, and its id. */
  async function openDraft(language: 'en' | 'de' = 'en', held?: Promise<void>) {
    await i18n.changeLanguage(language)
    saveDraft(
      { name: 'Old screener', description: WORKED_EXAMPLE_DESCRIPTION },
      { toolId: OLD_TOOL_ID, name: 'Old screener' },
    )
    server.use(saveHandler(null, held))
    const user = userEvent.setup()
    const rendered = renderRoute('/app/classify')
    await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
    return { user, ...rendered }
  }

  it.each([
    ['en', 'Adds a new check to Old screener.', 'Classify as a new tool instead'],
    ['de', 'Fügt eine neue Prüfung für Old screener hinzu.', 'Stattdessen als neues Tool prüfen'],
  ] as const)('says the run is added to that tool (%s)', async (language, note, action) => {
    await openDraft(language)
    expect(screen.getByText(note)).toBeVisible()
    expect(screen.getByRole('button', { name: action })).toBeVisible()
  })

  it('saves the run on that tool while the line is shown', async () => {
    const { user, router } = await openDraft()
    await user.click(screen.getByRole('button', { name: 'Run the checks' }))

    await expect.poll(() => saves.length).toBe(1)
    expect(saves[0]).toMatchObject({ target_system_id: OLD_TOOL_ID })
    // Let the run finish, or its late clearDraft() lands in the next test.
    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
  })

  it('keeps the old tool in the kept draft while the run is on', async () => {
    let release = (): void => undefined
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const { user, router } = await openDraft('en', held)
    await user.click(screen.getByRole('button', { name: 'Run the checks' }))

    // The save is held, so the run isn't finished and the draft hasn't been cleared yet.
    await expect.poll(() => saves.length).toBe(1)
    expect(readDraft().tool).toEqual({ toolId: OLD_TOOL_ID, name: 'Old screener' })

    release()
    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
  })

  it('"Classify as a new tool instead" lets the tool go: the next save creates a new tool', async () => {
    const { user, router } = await openDraft()
    await user.click(screen.getByRole('button', { name: 'Classify as a new tool instead' }))

    expect(screen.queryByText('Adds a new check to Old screener.')).toBeNull()
    // The kept draft forgets the tool too, so coming back later doesn't bring it back.
    expect(readDraft()).toEqual({
      values: { name: 'Old screener', description: WORKED_EXAMPLE_DESCRIPTION },
      tool: null,
    })
    await user.click(screen.getByRole('button', { name: 'Run the checks' }))

    await expect.poll(() => saves.length).toBe(1)
    expect(saves[0]).toMatchObject({ tool_name: 'Old screener', target_system_id: null })
    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
  })

  it('shows no line for a new tool', async () => {
    await i18n.changeLanguage('en')
    renderRoute('/app/classify')
    await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
    expect(screen.queryByRole('button', { name: 'Classify as a new tool instead' })).toBeNull()
  })
})
