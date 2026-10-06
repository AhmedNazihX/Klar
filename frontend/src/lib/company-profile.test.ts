import { describe, expect, it } from 'vitest'

import {
  classifyWriteFailure,
  deriveSizeClass,
  ImportFileError,
  STAFF_BANDS,
  TURNOVER_BANDS,
  type SizeClass,
  type StaffBand,
} from './company-profile'

// P19's derivation, copied from backend/tests/db/test_user_data_screens.py (SIZE_CLASSES), which
// checks the same table against the generated column inventories.size_class. One row per staff
// band, in TURNOVER_BANDS order.
const P19_SIZE_CLASSES: Record<StaffBand, readonly SizeClass[]> = {
  '1-9': ['sme', 'sme', 'smc', 'none'],
  '10-49': ['sme', 'sme', 'smc', 'none'],
  '50-249': ['sme', 'sme', 'smc', 'none'],
  '250-749': ['smc', 'smc', 'smc', 'none'],
  '750+': ['none', 'none', 'none', 'none'],
}

const TABLE = STAFF_BANDS.flatMap((staff) =>
  TURNOVER_BANDS.map(
    (turnover, index) => [staff, turnover, P19_SIZE_CLASSES[staff][index]] as const,
  ),
)

describe('deriveSizeClass', () => {
  it.each(TABLE)('%s staff, %s turnover: %s', (staff, turnover, expected) => {
    expect(deriveSizeClass(staff, turnover)).toBe(expected)
  })

  it('is null until both bands are set, like the column', () => {
    expect(deriveSizeClass(null, 'up_to_10m')).toBeNull()
    expect(deriveSizeClass('1-9', null)).toBeNull()
    expect(deriveSizeClass(null, null)).toBeNull()
  })
})

function postgrestError(code: string) {
  return { code, message: `server text for ${code}`, details: null, hint: null }
}

describe('classifyWriteFailure', () => {
  it.each([
    [postgrestError('PT507'), 'storage-full'],
    [postgrestError('PT413'), 'too-large'],
    [postgrestError('22023'), 'bad-file'],
    [postgrestError('22P02'), 'bad-file'],
    [postgrestError('23514'), 'bad-file'],
    [postgrestError('42501'), 'failed'],
    [new ImportFileError('not-json'), 'bad-file'],
    [new ImportFileError('too-large'), 'too-large'],
    [new Error('network'), 'failed'],
  ])('sorts an import failure %o as %s', (error, expected) => {
    expect(classifyWriteFailure(error, 'import')).toBe(expected)
  })

  it.each([
    [postgrestError('PT507'), 'storage-full'],
    [postgrestError('22023'), 'failed'],
    [postgrestError('22P02'), 'failed'],
    [postgrestError('22007'), 'failed'],
    [postgrestError('23502'), 'failed'],
    [postgrestError('23514'), 'failed'],
    [postgrestError('PT413'), 'failed'],
  ])('never calls a failed save a bad file: %o is %s', (error, expected) => {
    expect(classifyWriteFailure(error, 'save')).toBe(expected)
  })
})
