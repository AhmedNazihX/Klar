import { setupServer } from 'msw/node'

// The network boundary for tests. It starts with no handlers; a test adds its own with
// `server.use(...)`. Any request without a handler fails the test, so nothing reaches a real API.
export const server = setupServer()
