import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubReducedMotion } from '@/test/reduced-motion'

import { prefersReducedMotion, usePrefersReducedMotion } from './use-prefers-reduced-motion'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('usePrefersReducedMotion', () => {
  it('is true when the visitor asked for reduced motion', () => {
    stubReducedMotion(true)
    expect(prefersReducedMotion()).toBe(true)
    expect(renderHook(() => usePrefersReducedMotion()).result.current).toBe(true)
  })

  it('is false otherwise', () => {
    stubReducedMotion(false)
    expect(prefersReducedMotion()).toBe(false)
    expect(renderHook(() => usePrefersReducedMotion()).result.current).toBe(false)
  })

  it('is false where the browser cannot tell (no matchMedia)', () => {
    vi.stubGlobal('matchMedia', undefined)
    expect(prefersReducedMotion()).toBe(false)
    expect(renderHook(() => usePrefersReducedMotion()).result.current).toBe(false)
  })
})
