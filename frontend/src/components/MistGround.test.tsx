import { act, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { stubReducedMotion } from '@/test/reduced-motion'

import { MistGround } from './MistGround'

/** Frames run only when the test says so. */
function stubFrames(): { run: (count: number) => void } {
  let queue: FrameRequestCallback[] = []
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    queue.push(callback)
    return queue.length
  })
  vi.stubGlobal('cancelAnimationFrame', () => undefined)
  return {
    run(count) {
      for (let frame = 0; frame < count; frame += 1) {
        const due = queue
        queue = []
        for (const callback of due) callback(frame * 16)
      }
    },
  }
}

/** The cursor light's horizontal offset, in px, from its transform. */
function offsetX(light: HTMLElement | undefined): number {
  return Number(/translate3d\(([-\d.e]+)px/.exec(light?.style.transform ?? '')?.[1])
}

/** The cursor light's vertical offset, in px, from its transform. */
function offsetY(light: HTMLElement | undefined): number {
  return Number(/translate3d\([-\d.e]+px, ([-\d.e]+)px/.exec(light?.style.transform ?? '')?.[1])
}

/** Places the ground as if the page were scrolled `scrolled` px down. */
function scrollGroundTo(ground: HTMLElement, scrolled: number): void {
  vi.spyOn(ground, 'getBoundingClientRect').mockReturnValue(
    DOMRect.fromRect({ x: 0, y: -scrolled, width: 1440, height: 5000 }),
  )
}

function renderGround(): { ground: HTMLElement; light: (kind: string) => HTMLElement[] } {
  const { container } = render(
    <MistGround>
      <p>Page</p>
    </MistGround>,
  )
  const ground = container.querySelector<HTMLElement>('[data-ground="mist"]')
  if (!ground) throw new Error('no ground')
  return {
    ground,
    light: (kind) => Array.from(ground.querySelectorAll<HTMLElement>(`[data-light="${kind}"]`)),
  }
}

describe('MistGround', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  describe('with motion', () => {
    let frames: ReturnType<typeof stubFrames>
    beforeEach(() => {
      stubReducedMotion(false)
      frames = stubFrames()
    })

    it('lights the cursor light under the pointer and fades it when the pointer leaves', () => {
      const { ground, light } = renderGround()
      const [cursor] = light('cursor')
      fireEvent.pointerMove(ground, { clientX: 500, clientY: 400 })
      expect(cursor).toHaveAttribute('data-on')
      frames.run(1)
      // The light's centre (760 px wide) sits on the pointer.
      expect(cursor?.style.transform).toBe('translate3d(120px, 20px, 0)')
      fireEvent.pointerLeave(ground)
      expect(cursor).not.toHaveAttribute('data-on')
    })

    it('eases the cursor light 9% of the way each frame', () => {
      const { ground, light } = renderGround()
      const [cursor] = light('cursor')
      fireEvent.pointerMove(ground, { clientX: 380, clientY: 380 })
      frames.run(1)
      fireEvent.pointerMove(ground, { clientX: 480, clientY: 380 })
      frames.run(1)
      // 9% of the 100 px to go, then 9% of the 91 px left.
      expect(offsetX(cursor)).toBeCloseTo(9, 6)
      frames.run(1)
      expect(offsetX(cursor)).toBeCloseTo(9 + 91 * 0.09, 6)
    })

    it('keeps the cursor light under a still pointer while the page scrolls', () => {
      const { ground, light } = renderGround()
      const [cursor] = light('cursor')
      scrollGroundTo(ground, 0)
      fireEvent.pointerMove(ground, { clientX: 500, clientY: 400 })
      frames.run(1)
      expect(offsetY(cursor)).toBe(20)
      // The page scrolls 300 px under the pointer, which doesn't move on screen.
      scrollGroundTo(ground, 300)
      act(() => {
        window.dispatchEvent(new Event('scroll'))
      })
      frames.run(200)
      // 400 px down the screen is now 700 px down the ground; the light centres on it.
      expect(Math.abs(offsetY(cursor) - 320)).toBeLessThan(1)
      expect(offsetX(cursor)).toBe(120)
    })

    it('drifts the two lights at different speeds as the page scrolls', () => {
      const { ground, light } = renderGround()
      vi.spyOn(ground, 'getBoundingClientRect').mockReturnValue(
        DOMRect.fromRect({ x: 0, y: -500, width: 1440, height: 5000 }),
      )
      act(() => {
        window.dispatchEvent(new Event('scroll'))
      })
      frames.run(1)
      const [lightA, lightB] = light('drift')
      expect(lightA?.style.transform).toBe('translateY(160px)')
      expect(lightB?.style.transform).toBe('translateY(-100px)')
    })
  })

  it('keeps the lights still and drops the cursor light with reduced motion', () => {
    stubReducedMotion(true)
    const frames = stubFrames()
    const { ground, light } = renderGround()
    expect(light('cursor')).toEqual([])
    fireEvent.pointerMove(ground, { clientX: 500, clientY: 400 })
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })
    frames.run(2)
    for (const drift of light('drift')) expect(drift.style.transform).toBe('')
  })
})
