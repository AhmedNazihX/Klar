import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

// No Supabase in this file (the test environment sets none): nothing can be saved or imported.
describe('Welcome without Supabase', () => {
  it('disables Save and the import, and keeps Skip', async () => {
    renderRoute('/app/welcome')
    await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
    expect(screen.getByRole('button', { name: 'Save and add a tool' })).toBeDisabled()
    expect(screen.getByLabelText('Import your data')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Skip for now' })).toBeEnabled()
  })
})
