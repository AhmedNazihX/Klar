import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { cn, TYPE_SCALE } from './utils'

const tokens = JSON.parse(
  readFileSync(resolve(process.cwd(), '../docs/design-system/tokens.json'), 'utf-8'),
) as { type: { groups: { styles: { name: string }[] }[] } }

describe('cn', () => {
  it('knows exactly the design system’s type styles', () => {
    const styles = tokens.type.groups.flatMap((group) => group.styles.map((style) => style.name))
    expect([...TYPE_SCALE].sort()).toEqual(styles.sort())
  })

  it('keeps a type-scale size next to a text colour', () => {
    expect(cn('text-micro', 'text-slate')).toBe('text-micro text-slate')
    expect(cn('text-verdict text-ink')).toBe('text-verdict text-ink')
  })

  it('still resolves conflicts: the later size or padding wins', () => {
    expect(cn('text-micro', 'text-quote')).toBe('text-quote')
    expect(cn('p-7', 'p-8')).toBe('p-8')
  })
})
