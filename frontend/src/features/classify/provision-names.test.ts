import { describe, expect, it } from 'vitest'

import { longDate, monthsUntil, routeOfPoint } from './dates'
import { annexPointKey, isLawProvision, provisionName } from './provision-names'

describe('provisionName', () => {
  it.each([
    ['art:26:11', 'Art. 26(11)', 'Art. 26 Abs. 11'],
    ['art:50', 'Art. 50', 'Art. 50'],
    ['art:5:1:c:i', 'Art. 5(1)(c)(i)', 'Art. 5 Abs. 1 Buchst. c Ziff. i'],
    ['art:16:c', 'Art. 16(c)', 'Art. 16 Buchst. c'],
    ['annex:III:4:a', 'Annex III 4(a)', 'Anhang III Nr. 4 Buchst. a'],
    ['annex:III:2', 'Annex III 2', 'Anhang III Nr. 2'],
    ['annex:I:A:11', 'Annex I Section A point 11', 'Anhang I Abschnitt A Nr. 11'],
    ['recital:12', 'Recital 12', 'Erwägungsgrund 12'],
    [
      'guide:guide-prohibited:para:173',
      'Guidelines on prohibited practices, para. 173',
      'Leitlinien zu verbotenen Praktiken, Rn. 173',
    ],
    [
      'guide:guide-high-risk-annex-iii:ex:118',
      'Guidelines on high-risk classification, example 118',
      'Leitlinien zur Hochrisiko-Einstufung, Beispiel 118',
    ],
    ['guide:unknown:para:3', 'Commission guidelines, para. 3', 'Leitlinien der Kommission, Rn. 3'],
    ['something-else', 'something-else', 'something-else'],
  ])('names %s in English and German', (id, english, german) => {
    expect(provisionName(id, 'en')).toBe(english)
    expect(provisionName(id, 'de')).toBe(german)
  })

  it('tells the Act from recitals and guidance', () => {
    expect(isLawProvision('art:6:3')).toBe(true)
    expect(isLawProvision('annex:III:4:a')).toBe(true)
    expect(isLawProvision('recital:12')).toBe(false)
    expect(isLawProvision('guide:guide-art50:para:10')).toBe(false)
  })

  it('keys Annex III points for their plain labels', () => {
    expect(annexPointKey('annex:III:4:a')).toBe('III_4_a')
    expect(annexPointKey('annex:III:2')).toBe('III_2')
    expect(annexPointKey('annex:I:A:11')).toBeNull()
    expect(annexPointKey('art:6:3')).toBeNull()
  })
})

describe('dates', () => {
  it('writes long dates in English and German', () => {
    expect(longDate('2027-12-02', 'en')).toBe('2 December 2027')
    expect(longDate('2027-12-02', 'de')).toBe('2. Dezember 2027')
  })

  it('counts whole months to a date, and none once it has come', () => {
    const today = new Date(2026, 9, 7)
    expect(monthsUntil('2027-12-02', today)).toBe(14)
    expect(monthsUntil('2026-10-10', today)).toBe(1)
    expect(monthsUntil('2026-08-02', today)).toBe(0)
  })

  it('reads the route from an Annex point', () => {
    expect(routeOfPoint('annex:III:4:a')).toBe('annex_iii')
    expect(routeOfPoint('annex:I:A:11')).toBe('annex_i')
    expect(routeOfPoint(null)).toBeNull()
  })
})
