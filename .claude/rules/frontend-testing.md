---
paths:
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
  - "frontend/e2e/**"
  - "frontend/**/test-utils*"
---

# Frontend testing rules

**Tools:** Vitest, React Testing Library and `@testing-library/user-event` for components. Playwright for end-to-end
tests in `frontend/e2e/` (story P13). The backend runs in replay mode, so no test calls a live model.

**Component tests**
- Test what the user sees and does. Query in this order: `getByRole` (with `name`), then `getByLabelText`, then
  `getByText`. `data-testid` is a last resort. Never assert on internal state, hook calls or render counts.
- Call `userEvent.setup()` once per test, and `await` every interaction. Use `findBy*` and `waitFor` for async work. Never `setTimeout`.
- Render with the shared `renderWithProviders` from `test-utils.tsx`: a fresh `QueryClient` per test with retries
  off, i18n, and the router.
- Mock at the network boundary, with MSW handlers returning fixtures typed from the generated client. Don't mock
  React, hooks or child components.
- No snapshot tests of components.
- Run an `axe` check (`vitest-axe`) on the key views: the classification form, the result summary, the reviewer
  view and the inventory table.

**What must be covered**
- Each result status renders distinctly: decided, `needs_more_information`, `legally_ambiguous`. The working
  assumption is labelled.
- The disclaimer and AI disclosure appear on every result view.
- Key screens render in German with no missing keys. P11 adds a key-coverage test.

**End-to-end tests**
- Use deterministic waits for elements and responses only, never fixed timeouts.
- Check keyboard navigation through the main flow.
- Take screenshots of key screens at 375 px and 1280 px.
