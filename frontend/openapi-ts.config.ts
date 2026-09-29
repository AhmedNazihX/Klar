// `pnpm gen:api`: generates the typed API client in src/api/ from the FastAPI OpenAPI schema.
// The schema is frontend/openapi.json, exported by the API (story P1). To read it from a running
// API instead, set OPENAPI_INPUT, e.g. OPENAPI_INPUT=http://localhost:8000/openapi.json.
// src/api/ is generated output: never edit it by hand, regenerate it after the API changes.
import { existsSync } from 'node:fs'

import { defineConfig } from '@hey-api/openapi-ts'

const input = process.env['OPENAPI_INPUT'] ?? './openapi.json'

if (!/^https?:\/\//.test(input) && !existsSync(input)) {
  throw new Error(
    `No OpenAPI schema at ${input}. It is exported from the FastAPI app (story P1); ` +
      'or set OPENAPI_INPUT to the running API, e.g. http://localhost:8000/openapi.json.',
  )
}

export default defineConfig({
  input,
  output: { path: 'src/api' },
  plugins: [
    '@hey-api/typescript',
    '@hey-api/sdk',
    // The base URL comes from VITE_API_URL at runtime (src/lib/api-client-config.ts).
    { name: '@hey-api/client-fetch', runtimeConfigPath: './src/lib/api-client-config.ts' },
    // queryOptions/mutationOptions for TanStack Query: views wrap these in their own hooks.
    '@tanstack/react-query',
  ],
})
