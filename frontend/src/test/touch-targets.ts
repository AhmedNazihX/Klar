// The phone's touch-target rule (WCAG 2.5.5, P26): every control a finger can hit is at least
// 44 px each way. Shared by the result's phone test and the other app screens' (P31).

/** The smallest touch target, in px. */
export const MIN_TARGET_PX = 44

const CONTROLS = 'a[href], button, input, textarea, select, summary'

/** Every control under `root` a finger can hit: those shown, hidden ones left out. */
export function shownControls(root: ParentNode = document): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(CONTROLS)].filter(
    (element) => element.getClientRects().length > 0,
  )
}

/** Whether the element stretches over its positioned ancestor with an absolute `::after` (a whole
 *  table row as one link, InventoryTable): the finger hits that ancestor. */
function isStretched(element: HTMLElement): boolean {
  const after = getComputedStyle(element, '::after')
  return after.content !== 'none' && after.position === 'absolute'
}

/** The box a finger can hit: a checkbox's or a radio's is the label around it, a stretched
 *  link's the box it stretches over. */
export function targetBox(element: HTMLElement): DOMRect {
  const stretchedOver = isStretched(element) ? element.offsetParent : null
  return (stretchedOver ?? element.closest('label') ?? element).getBoundingClientRect()
}

/** Every shown control under `root` smaller than 44 px either way, described for the failure
 *  message ("BUTTON "Show all" 120x20"); none when the screen keeps the rule. */
export function smallTouchTargets(root: ParentNode = document): string[] {
  return shownControls(root)
    .map((element) => ({ element, box: targetBox(element) }))
    .filter(({ box }) => box.width < MIN_TARGET_PX || box.height < MIN_TARGET_PX)
    .map(
      ({ element, box }) =>
        `${element.tagName} "${element.getAttribute('aria-label') ?? element.textContent}" ${String(Math.round(box.width))}x${String(Math.round(box.height))}`,
    )
}
