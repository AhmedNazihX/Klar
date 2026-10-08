// VersionDiff in a real browser: a date or an Annex point stays on one line even in a column
// narrower than its text (its `whitespace-nowrap`), while a text value wraps between words.
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { VersionDiff, type VersionDiffRow } from './VersionDiff'

const NARROW_PX = 190

/** How many lines a cell's value takes: its text's line boxes, counted by their distinct tops. */
function lineCount(cell: Element): number {
  const value = cell.lastElementChild
  if (!value) throw new Error('A cell holds its value.')
  const range = document.createRange()
  range.selectNodeContents(value)
  return new Set(Array.from(range.getClientRects(), (rect) => Math.round(rect.top))).size
}

function renderNarrow(rows: readonly VersionDiffRow[]): HTMLElement {
  render(
    <div style={{ width: NARROW_PX }}>
      <VersionDiff rows={rows} />
    </div>,
  )
  return screen.getByRole('table')
}

describe('VersionDiff in a column narrower than its values', () => {
  it('keeps a date on one line', () => {
    const table = renderNarrow([
      {
        id: 'date',
        label: 'From',
        before: '2 December 2027',
        after: '2 August 2026',
        kind: 'date',
      },
    ])
    expect(within(table).getAllByRole('cell').map(lineCount)).toEqual([1, 1])
  })

  it('keeps an Annex point on one line when the rows stack', () => {
    const table = renderNarrow([
      {
        id: 'basis',
        label: 'Basis',
        before: 'Annex I Section B point 21',
        after: 'Annex III point 4',
        kind: 'reference',
      },
    ])
    expect(within(table).getAllByRole('cell').map(lineCount)).toEqual([1, 1])
  })

  it('lets a text value wrap between words', () => {
    const table = renderNarrow([
      {
        id: 'class',
        label: 'Class',
        before: 'High risk, assumed class',
        after: 'Limited risk, assumed class',
      },
    ])
    expect(Math.max(...within(table).getAllByRole('cell').map(lineCount))).toBeGreaterThan(1)
  })
})
