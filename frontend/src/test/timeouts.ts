// How long tests wait for the page to settle. Both setup files make it testing-library's default
// (`findBy*`, `waitFor`); Vitest's own `vi.waitFor` and `expect.poll` take it explicitly.

/** A screen's first render loads its lazy route chunks cold, which can pass a second in a full
 *  run, more so beside another worktree's run (F10). */
export const FIRST_RENDER_MS = 5000
