---
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/.env*"
  - "frontend/vite.config.*"
---

# Frontend security rules

**No secrets in the frontend.** Every `VITE_*` variable is shipped in the public bundle. The frontend holds only
`VITE_API_URL`, `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. The OpenRouter key, the Supabase service key and
any other secret stay on the server.

**Treat model output, user descriptions and quoted legal text as untrusted**
- Render them as text. If markdown is needed, use `react-markdown` **without** raw HTML: no `rehype-raw`, no `dangerouslySetInnerHTML`.
- If raw HTML is ever truly unavoidable, sanitise it with DOMPurify at the same place it's rendered, and flag it for review.
- Dynamic links (for example to EUR-Lex) are allowed only with `http:` or `https:` schemes, checked with `new URL()`.
  `target="_blank"` always needs `rel="noopener noreferrer"`.

**Sessions**
- supabase-js keeps the anonymous session in `localStorage` by default. That's accepted for the MVP, because the
  session is anonymous and has no credentials (INIT › Storage).
- The consequence is that an XSS bug means session theft, so the untrusted-content rules above are strict.
  Revisit this when real accounts arrive (story S3).
- The UI never decides who may see what: RLS and the API enforce it. Hiding something in the UI is presentation, not security.

**Personal data:** warn the user before sending a description that seems to contain personal data (story P12).

**Dependencies and build**
- Commit the lockfile. Before adding a UI library, check that it doesn't render raw HTML from its props.
- Production builds don't serve source maps publicly. The Content Security Policy and security headers are set at deployment (story S3).
