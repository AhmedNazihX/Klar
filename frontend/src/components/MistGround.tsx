import { useEffect, useRef, type JSX, type ReactNode } from 'react'

import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion'
import { cn } from '@/lib/utils'

/** The cursor light closes this share of the distance to the pointer each frame. */
export const CURSOR_EASING = 0.09
// How far each drifting light moves per pixel scrolled: one with the page, one against it.
const DRIFT_A = 0.32
const DRIFT_B = -0.2
// Half the cursor light's 760 px, so its centre sits on the pointer.
const CURSOR_LIGHT_RADIUS = 380
// Below this distance (px) the cursor light has arrived and the frame loop stops.
const SETTLED_PX = 0.5

type Point = { x: number; y: number }

/**
 * Moves the lights: the drifting pair follow the scroll, the cursor light eases after the pointer
 * and fades out when it leaves. Returns the clean-up.
 */
function startLights(ground: HTMLElement, lights: HTMLElement[], cursor: HTMLElement): () => void {
  let scrollFrame = 0
  let cursorFrame = 0
  let at: Point = { x: 0, y: 0 }
  let target: Point = { x: 0, y: 0 }
  // The pointer on screen: a scroll moves the ground under it without a pointer event.
  let pointer: Point = { x: 0, y: 0 }
  let isOn = false

  function aimAtPointer(): void {
    const box = ground.getBoundingClientRect()
    target = { x: pointer.x - box.left, y: pointer.y - box.top }
    if (!cursorFrame) cursorFrame = requestAnimationFrame(follow)
  }

  function follow(): void {
    at = {
      x: at.x + (target.x - at.x) * CURSOR_EASING,
      y: at.y + (target.y - at.y) * CURSOR_EASING,
    }
    cursor.style.transform = `translate3d(${at.x - CURSOR_LIGHT_RADIUS}px, ${at.y - CURSOR_LIGHT_RADIUS}px, 0)`
    const isMoving =
      Math.abs(target.x - at.x) > SETTLED_PX || Math.abs(target.y - at.y) > SETTLED_PX
    cursorFrame = isMoving ? requestAnimationFrame(follow) : 0
  }

  function onPointerMove(event: PointerEvent): void {
    pointer = { x: event.clientX, y: event.clientY }
    aimAtPointer()
    if (!isOn) {
      isOn = true
      at = target
      cursor.dataset.on = 'true'
    }
  }

  function onPointerLeave(): void {
    isOn = false
    delete cursor.dataset.on
  }

  function onScroll(): void {
    if (scrollFrame) return
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0
      const offset = Math.max(0, -ground.getBoundingClientRect().top)
      const [lightA, lightB] = lights
      if (lightA) lightA.style.transform = `translateY(${offset * DRIFT_A}px)`
      if (lightB) lightB.style.transform = `translateY(${offset * DRIFT_B}px)`
      if (isOn) aimAtPointer()
    })
  }

  ground.addEventListener('pointermove', onPointerMove)
  ground.addEventListener('pointerleave', onPointerLeave)
  window.addEventListener('scroll', onScroll, { passive: true })
  return () => {
    ground.removeEventListener('pointermove', onPointerMove)
    ground.removeEventListener('pointerleave', onPointerLeave)
    window.removeEventListener('scroll', onScroll)
    cancelAnimationFrame(scrollFrame)
    cancelAnimationFrame(cursorFrame)
  }
}

/**
 * The root of a public page (components.md › MistGround): the mist ground with its four mesh
 * lights, plus two softer lights that drift at different speeds as the page scrolls and a Lens blue
 * light that trails the cursor, all behind the glass. Reduced motion keeps them still and drops
 * the cursor light. One per page; the app uses the still ground only.
 */
export function MistGround({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}): JSX.Element {
  const isReducedMotion = usePrefersReducedMotion()
  const groundRef = useRef<HTMLDivElement>(null)
  const lightARef = useRef<HTMLDivElement>(null)
  const lightBRef = useRef<HTMLDivElement>(null)
  const cursorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ground = groundRef.current
    const cursor = cursorRef.current
    if (isReducedMotion || !ground || !cursor) return
    const lights = [lightARef.current, lightBRef.current].filter(
      (light): light is HTMLDivElement => light !== null,
    )
    return startLights(ground, lights, cursor)
  }, [isReducedMotion])

  return (
    <div
      ref={groundRef}
      data-ground="mist"
      className={cn('relative isolate min-h-dvh overflow-x-clip bg-ground', className)}
    >
      <div className="ground-lights" aria-hidden="true">
        <div ref={lightARef} data-light="drift" className="ground-light ground-light-a" />
        <div ref={lightBRef} data-light="drift" className="ground-light ground-light-b" />
        {!isReducedMotion && <div ref={cursorRef} data-light="cursor" className="ground-cursor" />}
      </div>
      {children}
    </div>
  )
}
