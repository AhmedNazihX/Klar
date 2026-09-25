---
paths:
  - "backend/aiact/api/**"
  - "backend/aiact/mcp/**"
---

# API and MCP rules (FastAPI, MCP server)

Both are **thin clients of the engine** (INIT › Tech stack). They validate input, call the engine or retrieval
functions, and return the result. No classification logic lives here.

**Shape**
- Build the app in `create_app()`. Keep routers thin, and put settings, the database and the current session in dependencies.
- Request and response bodies are Pydantic models. Every endpoint that returns data sets `response_model`.
- The response for a classification *is* `aiact.schemas.ClassificationResult`. Don't make a parallel API model for it.
- Every result, and every MCP tool output, carries the law version and the disclaimer.
- `POST /classify` streams step events over SSE, then the final result. Handle a client disconnect by cancelling the run.
- After any API change, export the schema to `frontend/openapi.json`. The frontend's client is generated from that file.
- MCP tools wrap the same functions as the API and return the same Pydantic outputs (INIT › MCP tools).

**Async:** endpoints doing I/O are `async def`, and use async clients only. No `requests`, sync database drivers or
blocking file I/O inside routes.

**Auth and data**
- Users are Supabase (anonymous) sessions. Verify the JWT's signature, expiry, audience and issuer.
- Query user data with the user's JWT, so that RLS applies. The service key is never used on behalf of a user.
- Authorisation is enforced by RLS and the API, never by what the UI shows or hides.

**Abuse and cost:** rate-limit `/classify` and `/qa`, and enforce the spending cap. The OpenRouter key lives on the
server and never appears in any response.

**CORS:** origins come from the settings, per environment. Never a wildcard origin together with credentials.

**Logging:** log metadata only (IDs, timings, token counts, status). Never log descriptions, answers, `Authorization`
headers or cookies.

**Tests:** use an httpx `AsyncClient` with the ASGI transport. Run the engine in replay mode. Override the exact
dependency the route uses, and clear `app.dependency_overrides` after each test.
