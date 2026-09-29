import { describe, expect, it } from 'vitest'

import { readEnv } from './env'

describe('readEnv', () => {
  it('falls back to the local API and no Supabase when nothing is set', () => {
    expect(readEnv({})).toEqual({ apiUrl: 'http://localhost:8000', supabase: null })
  })

  it('treats blank values as unset', () => {
    expect(readEnv({ VITE_SUPABASE_URL: '', VITE_SUPABASE_ANON_KEY: '' }).supabase).toBeNull()
  })

  it('reads a complete configuration', () => {
    const env = readEnv({
      VITE_API_URL: 'https://api.example.test',
      VITE_SUPABASE_URL: 'http://127.0.0.1:54321',
      VITE_SUPABASE_ANON_KEY: 'public-anon-key',
    })
    expect(env).toEqual({
      apiUrl: 'https://api.example.test',
      supabase: { url: 'http://127.0.0.1:54321', anonKey: 'public-anon-key' },
    })
  })

  it('needs both Supabase values before it builds a client config', () => {
    expect(readEnv({ VITE_SUPABASE_URL: 'http://127.0.0.1:54321' }).supabase).toBeNull()
  })

  it('names the variable that is not a http(s) URL', () => {
    expect(() => readEnv({ VITE_API_URL: 'javascript:alert(1)' })).toThrow(/VITE_API_URL/)
  })
})
