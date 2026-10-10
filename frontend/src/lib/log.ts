/** The error's code (a Postgres or PostgREST code), if it has one. */
function codeOf(error: unknown): string | null {
  if (typeof error !== 'object' || error === null || !('code' in error)) return null
  return typeof error.code === 'string' ? error.code : null
}

/**
 * Logs a failure the screen goes on without: a read that only adds to what is shown (P5b). Only
 * the fixed message and the error's code reach the console, never the error itself, which can
 * carry the user's own text (a description, an answer).
 */
export function logSkippedRead(message: string, error: unknown): void {
  // eslint-disable-next-line no-console -- the one place the app logs a failure it goes on without
  console.warn(message, codeOf(error) ?? 'no code')
}
