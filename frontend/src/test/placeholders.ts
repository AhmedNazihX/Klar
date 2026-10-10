// Checks that every unknown on a page is a marked placeholder (the system's `.kl-ph`, the
// Placeholder component's `data-placeholder`), for the site pages (P17).

const BRACKETED = /\[[^\]]*\]/g

function textNodes(root: HTMLElement): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) nodes.push(node as Text)
  return nodes
}

/** The bracketed fields in `root` (e.g. "[NAME]") that sit outside a marked placeholder. */
export function unmarkedPlaceholders(root: HTMLElement): string[] {
  return textNodes(root).flatMap((node) =>
    node.parentElement?.closest('[data-placeholder]')
      ? []
      : Array.from(node.data.matchAll(BRACKETED), (match) => match[0]),
  )
}

/** The text of every marked placeholder in `root`, in page order. */
export function markedPlaceholders(root: HTMLElement): string[] {
  return Array.from(root.querySelectorAll('[data-placeholder]'), (node) => node.textContent)
}
