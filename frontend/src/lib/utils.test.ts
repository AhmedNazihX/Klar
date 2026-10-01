import { describe, expect, it } from 'vitest'

import { cn } from './utils'

describe('cn', () => {
  it('keeps a type-scale size next to a text colour', () => {
    expect(cn('text-micro', 'text-slate')).toBe('text-micro text-slate')
    expect(cn('text-verdict text-ink')).toBe('text-verdict text-ink')
  })

  it('still resolves conflicts: the later size or padding wins', () => {
    expect(cn('text-micro', 'text-quote')).toBe('text-quote')
    expect(cn('p-7', 'p-8')).toBe('p-8')
  })
})
