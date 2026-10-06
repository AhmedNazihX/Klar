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

describe('classifyWriteFailure', () => {
  it.each([
    [{ code: 'PT507', message: 'storage full', details: null, hint: 'Delete' }, 'storage-full'],
    [{ code: 'PT413', message: 'too large', details: null, hint: null }, 'too-large'],
    [{ code: '22023', message: 'not an export', details: null, hint: null }, 'bad-file'],
    [{ code: '42501', message: 'denied', details: null, hint: null }, 'failed'],
    [new ImportFileError('not-json'), 'bad-file'],
    [new ImportFileError('too-large'), 'too-large'],
    [new Error('network'), 'failed'],
  ])('sorts %o as %s', (error, expected) => {
    expect(classifyWriteFailure(error)).toBe(expected)
  })
})
